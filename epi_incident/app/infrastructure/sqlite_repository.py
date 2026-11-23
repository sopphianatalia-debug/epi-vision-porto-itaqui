"""
SqliteIncidentRepository — mesmo contrato do IncidentRepository, com persistência em SQLite.

Os incidentes (e a trilha de revisão) sobrevivem a reinício. Guarda cada incidente como JSON
(sem biometria nem imagem). O serviço chama `persist()` a cada mudança; o arquivo nunca apaga
incidentes (histórico auditável).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional

from app.domain.enums import IncidentStatus, Severity, ViolationType
from app.domain.models import Incident
from app.infrastructure.repository import IncidentRepository


def _dt(v: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(v) if v else None


def incident_to_record(i: Incident) -> dict:
    return {
        "incident_id": i.incident_id, "employee_id": i.employee_id, "rule_id": i.rule_id,
        "rule_version": i.rule_version, "ppe_type": i.ppe_type, "violation_type": i.violation_type.value,
        "reason_code": i.reason_code, "reason": i.reason, "severity": i.severity.value,
        "status": i.status.value, "opened_at": i.opened_at.isoformat(), "updated_at": i.updated_at.isoformat(),
        "first_evaluation_id": i.first_evaluation_id, "last_evaluation_id": i.last_evaluation_id,
        "occurrence_count": i.occurrence_count, "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
        "source": i.source, "source_cameras": list(i.source_cameras), "metadata": i.metadata,
        "review_status": i.review_status, "reviewed_by": i.reviewed_by,
        "reviewed_by_role": i.reviewed_by_role, "reviewer_verified": i.reviewer_verified,
        "reviewed_at": i.reviewed_at.isoformat() if i.reviewed_at else None,
        "review_note": i.review_note, "review_history": list(i.review_history),
        "processed_eval_ids": sorted(i._processed_eval_ids),
    }


def incident_from_record(d: dict) -> Incident:
    inc = Incident(
        incident_id=d["incident_id"], employee_id=d["employee_id"], rule_id=d["rule_id"],
        rule_version=d["rule_version"], ppe_type=d["ppe_type"], violation_type=ViolationType(d["violation_type"]),
        reason_code=d["reason_code"], reason=d["reason"], severity=Severity(d["severity"]),
        status=IncidentStatus(d["status"]), opened_at=_dt(d["opened_at"]), updated_at=_dt(d["updated_at"]),
        first_evaluation_id=d.get("first_evaluation_id"), last_evaluation_id=d.get("last_evaluation_id"),
        occurrence_count=d.get("occurrence_count", 1), resolved_at=_dt(d.get("resolved_at")),
        source=d.get("source", "rules_engine"), source_cameras=list(d.get("source_cameras", [])),
        metadata=dict(d.get("metadata", {})), review_status=d.get("review_status", "PENDING"),
        reviewed_by=d.get("reviewed_by"), reviewed_by_role=d.get("reviewed_by_role"),
        reviewer_verified=bool(d.get("reviewer_verified", False)), reviewed_at=_dt(d.get("reviewed_at")),
        review_note=d.get("review_note"), review_history=list(d.get("review_history", [])),
    )
    inc._processed_eval_ids = set(d.get("processed_eval_ids", []))
    return inc


class SqliteIncidentRepository(IncidentRepository):
    def __init__(self, path: str, id_prefix: str = "INC-", id_width: int = 6, max_history: int = 0) -> None:
        super().__init__(id_prefix, id_width, 0)   # sem poda: histórico auditável
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS incidents (seq INTEGER PRIMARY KEY, incident_id TEXT UNIQUE NOT NULL, data TEXT NOT NULL)")
        self._db.commit()
        self._load()

    def _load(self) -> None:
        for seq, data in self._db.execute("SELECT seq, data FROM incidents ORDER BY seq"):
            inc = incident_from_record(json.loads(data))
            self._by_id[inc.incident_id] = inc
            if inc.status == IncidentStatus.OPEN:
                self._open_by_key[inc.key] = inc.incident_id
            self._seq = max(self._seq, seq)

    def _seq_of(self, incident_id: str) -> int:
        digits = "".join(ch for ch in incident_id if ch.isdigit())
        return int(digits) if digits else 0

    def persist(self, incident: Incident) -> None:
        payload = json.dumps(incident_to_record(incident), ensure_ascii=False)
        with self._lock:
            self._db.execute("INSERT INTO incidents (seq, incident_id, data) VALUES (?, ?, ?) "
                             "ON CONFLICT(incident_id) DO UPDATE SET data = excluded.data",
                             (self._seq_of(incident.incident_id), incident.incident_id, payload))
            self._db.commit()

    def add(self, incident: Incident) -> Incident:
        super().add(incident)
        self.persist(incident)
        return incident

    def close(self) -> None:
        self._db.close()

"""
Serviço de evidências (seção 12 do spec).

Ao detectar não conformidade, registra a evidência: event_id, camera_id,
timestamp, frame_reference, employee_id, ppe_type, status, confidence.
Por padrão NÃO guarda a imagem (apenas a referência) — retenção configurável
(privacidade/LGPD).
"""
from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.enums import ComplianceStatus, PPEStatus
from app.types import ComplianceResult

_VIOLATION = {PPEStatus.MISSING, PPEStatus.IMPROPER}


class EvidenceService:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._store: deque[dict] = deque(maxlen=settings.evidence_max_entries)

    def maybe_capture(self, result: ComplianceResult, overall: ComplianceStatus) -> list[dict]:
        if overall not in (ComplianceStatus.NON_COMPLIANT, ComplianceStatus.PARTIAL_NON_COMPLIANCE):
            return []

        captured: list[dict] = []
        items = {
            "helmet": result.helmet.status,
            "vest": result.vest.status,
            "glove_left": result.glove_left.status,
            "glove_right": result.glove_right.status,
            "glasses": result.glasses.status,
            "boots": result.boots.status,
        }
        for ppe_type, status in items.items():
            if status in _VIOLATION:
                evidence = {
                    "event_id": str(uuid.uuid4()),
                    "camera_id": result.camera_id,
                    "timestamp": result.timestamp,
                    "frame_reference": None,  # preenchido pela camada de ingestão
                    "employee_id": result.employee_id,
                    "person_track_id": result.person_track_id,
                    "ppe_type": ppe_type,
                    "status": status.value,
                    "confidence": round(getattr(result, ppe_type).confidence, 4),
                    "image_stored": self._s.evidence_store_image,
                }
                self._store.append(evidence)
                captured.append(evidence)
        return captured

    def purge_expired(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._s.evidence_retention_days)
        keep = deque(
            (e for e in self._store if self._parse(e["timestamp"]) >= cutoff),
            maxlen=self._store.maxlen,
        )
        self._store = keep

    @staticmethod
    def _parse(ts: str) -> datetime:
        try:
            dt = datetime.fromisoformat(ts)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)

    def recent(self, limit: int = 50) -> list[dict]:
        return list(self._store)[-limit:][::-1]

    @property
    def count(self) -> int:
        return len(self._store)

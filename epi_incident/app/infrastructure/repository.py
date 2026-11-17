"""
IncidentRepository — estado em memória atrás de interface (padrão dos módulos
anteriores). IDs sequenciais determinísticos, índice de incidentes ABERTOS por
chave de deduplicação, e histórico imutável (sem DELETE).
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Iterable, Optional

from app.domain.models import Incident


class IncidentRepository:
    def __init__(self, id_prefix: str = "INC-", id_width: int = 6, max_history: int = 0) -> None:
        self._id_prefix = id_prefix
        self._id_width = id_width
        self._max_history = max_history
        self._seq = 0
        self._by_id: "OrderedDict[str, Incident]" = OrderedDict()
        self._open_by_key: dict[str, str] = {}  # dedup_key -> incident_id (só ABERTOS)

    def next_id(self) -> str:
        self._seq += 1
        return f"{self._id_prefix}{self._seq:0{self._id_width}d}"

    def add(self, incident: Incident) -> Incident:
        self._by_id[incident.incident_id] = incident
        self._open_by_key[incident.key] = incident.incident_id
        self._prune()
        return incident

    def get(self, incident_id: str) -> Optional[Incident]:
        return self._by_id.get(incident_id)

    def open_by_key(self, key: str) -> Optional[Incident]:
        iid = self._open_by_key.get(key)
        return self._by_id.get(iid) if iid else None

    def mark_resolved_in_index(self, incident: Incident) -> None:
        """Remove do índice de abertos (o incidente permanece no histórico)."""
        if self._open_by_key.get(incident.key) == incident.incident_id:
            del self._open_by_key[incident.key]

    def open_for_employee_rule(self, employee_id: str, rule_id: str) -> list[Incident]:
        return [
            self._by_id[iid] for iid in self._open_by_key.values()
            if (inc := self._by_id[iid]).employee_id == employee_id and inc.rule_id == rule_id
        ]

    def all(self) -> list[Incident]:
        return list(self._by_id.values())

    def filter(
        self,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        ppe_type: Optional[str] = None,
    ) -> list[Incident]:
        out: list[Incident] = []
        for inc in self._by_id.values():
            if employee_id and inc.employee_id != employee_id:
                continue
            if status and inc.status.value != status:
                continue
            if severity and inc.severity.value != severity:
                continue
            if ppe_type and inc.ppe_type != ppe_type:
                continue
            out.append(inc)
        return out

    def _prune(self) -> None:
        if self._max_history and len(self._by_id) > self._max_history:
            # remove os mais antigos JÁ RESOLVIDOS (preserva abertos e auditoria recente)
            for iid, inc in list(self._by_id.items()):
                if len(self._by_id) <= self._max_history:
                    break
                if inc.status.value == "RESOLVED":
                    del self._by_id[iid]

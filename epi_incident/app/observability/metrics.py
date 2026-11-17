"""Métricas simples do Incident Service (seção 40)."""
from __future__ import annotations

from collections import defaultdict
from threading import Lock

from app.domain.enums import Severity


class IncidentMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._created = 0
        self._resolved = 0
        self._open = 0
        self._by_severity: dict[str, int] = defaultdict(int)
        self._by_ppe: dict[str, int] = defaultdict(int)

    def record_created(self, severity: Severity, ppe_type: str) -> None:
        with self._lock:
            self._created += 1
            self._open += 1
            self._by_severity[severity.value] += 1
            self._by_ppe[ppe_type] += 1

    def record_resolved(self) -> None:
        with self._lock:
            self._resolved += 1
            self._open = max(0, self._open - 1)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "incidents_created": self._created,
                "incidents_resolved": self._resolved,
                "incidents_open": self._open,
                "incidents_by_severity": dict(self._by_severity),
                "incidents_by_ppe_type": dict(self._by_ppe),
            }


metrics = IncidentMetrics()

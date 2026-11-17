"""Métricas de observabilidade (seção 38)."""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock

from app.domain.enums import ComplianceStatus


class RulesMetrics:
    def __init__(self, window: int = 500) -> None:
        self._lock = Lock()
        self._evaluated = 0
        self._latencies = deque(maxlen=window)
        self._by_status: dict[str, int] = defaultdict(int)
        self._violations_detected = 0
        self._violations_resolved = 0
        self._low_confidence = 0
        self._by_area: dict[str, int] = defaultdict(int)
        self._by_operation: dict[str, int] = defaultdict(int)
        self._by_role: dict[str, int] = defaultdict(int)

    def record_evaluation(self, status: ComplianceStatus, latency_ms: float,
                          area: str | None, operation: str | None, role: str | None) -> None:
        with self._lock:
            self._evaluated += 1
            self._latencies.append(latency_ms)
            self._by_status[status.value] += 1
            if area:
                self._by_area[area] += 1
            if operation:
                self._by_operation[operation] += 1
            if role:
                self._by_role[role] += 1

    def record_violation_detected(self, n: int = 1) -> None:
        with self._lock:
            self._violations_detected += n

    def record_violation_resolved(self, n: int = 1) -> None:
        with self._lock:
            self._violations_resolved += n

    def record_low_confidence(self, n: int = 1) -> None:
        with self._lock:
            self._low_confidence += n

    def snapshot(self) -> dict:
        with self._lock:
            avg = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
            return {
                "rules_evaluated_total": self._evaluated,
                "rules_evaluation_latency_ms": round(avg, 3),
                "compliance_compliant_total": self._by_status.get("COMPLIANT", 0),
                "compliance_non_compliant_total": self._by_status.get("NON_COMPLIANT", 0),
                "compliance_indeterminate_total": self._by_status.get("INDETERMINATE", 0)
                    + self._by_status.get("PARTIAL", 0),
                "violations_detected_total": self._violations_detected,
                "violations_resolved_total": self._violations_resolved,
                "low_confidence_evaluations_total": self._low_confidence,
                "rules_by_area": dict(self._by_area),
                "rules_by_operation": dict(self._by_operation),
                "rules_by_employee_role": dict(self._by_role),
            }


metrics = RulesMetrics()

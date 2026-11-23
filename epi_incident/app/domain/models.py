"""Entidades de domínio do Incident Service."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.enums import REVIEW_PENDING, IncidentStatus, OverallStatus, Severity, ViolationType


def dedup_key(employee_id: str, rule_id: str, ppe_type: str, violation_type: str) -> str:
    """Chave lógica do incidente. Deliberadamente NÃO inclui camera_id: a mesma
    violação vista por várias câmeras é UMA ocorrência do funcionário."""
    return f"{employee_id}|{rule_id}|{ppe_type}|{violation_type}"


# --------------------------------------------------------------------------- #
# Entrada (produzida pelo Rules Engine)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ViolationInput:
    employee_id: str
    rule_id: str
    ppe_type: str
    reason_code: str
    reason: str
    severity: Severity
    rule_version: int = 1
    violation_type: ViolationType = ViolationType.PPE_VIOLATION
    evaluation_id: Optional[str] = None
    observed_status: Optional[str] = None
    source_cameras: tuple[str, ...] = ()
    metadata: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return dedup_key(self.employee_id, self.rule_id, self.ppe_type, self.violation_type.value)

    @staticmethod
    def _reason_code_from_status(observed_status: Optional[str]) -> str:
        return {
            "MISSING": "PPE_MISSING",
            "IMPROPER": "PPE_IMPROPER",
        }.get((observed_status or "").upper(), "PPE_VIOLATION")

    @classmethod
    def from_rules_violation(cls, v: dict, evaluation_id: Optional[str]) -> "ViolationInput":
        """Adapta um Violation.to_dict() do Rules Engine. O Rules Engine expõe
        `observed_status`+`reason` (não `reason_code`); derivamos o reason_code do
        status observado, de forma explícita e documentada."""
        return cls(
            employee_id=v["employee_id"],
            rule_id=v["rule_id"],
            rule_version=v.get("rule_version", 1),
            ppe_type=v["ppe_type"],
            observed_status=v.get("observed_status"),
            reason_code=v.get("reason_code") or cls._reason_code_from_status(v.get("observed_status")),
            reason=v.get("reason", ""),
            severity=Severity(v["severity"]),
            evaluation_id=evaluation_id,
            source_cameras=tuple(v.get("source_cameras", ())),
        )


@dataclass(frozen=True)
class EvaluationInput:
    """Espelha o ComplianceEvaluation do Rules Engine (para process_evaluation)."""

    employee_id: Optional[str]
    overall_status: OverallStatus
    effective_rule_id: Optional[str]
    violations: tuple[ViolationInput, ...]
    evaluation_id: Optional[str] = None
    timestamp: Optional[datetime] = None

    @classmethod
    def from_rules_dict(cls, d: dict) -> "EvaluationInput":
        eid = d.get("evaluation_id")
        return cls(
            employee_id=d.get("employee_id"),
            overall_status=OverallStatus(d["overall_status"]),
            effective_rule_id=d.get("effective_rule_id"),
            evaluation_id=eid,
            violations=tuple(ViolationInput.from_rules_violation(v, eid) for v in d.get("violations", [])),
        )


# --------------------------------------------------------------------------- #
# Entidade Incident (mutável: o status muda ao longo do ciclo de vida)
# --------------------------------------------------------------------------- #
@dataclass
class Incident:
    incident_id: str
    employee_id: str
    rule_id: str
    rule_version: int
    ppe_type: str
    violation_type: ViolationType
    reason_code: str
    reason: str
    severity: Severity
    status: IncidentStatus
    opened_at: datetime
    updated_at: datetime
    first_evaluation_id: Optional[str]
    last_evaluation_id: Optional[str]
    occurrence_count: int = 1
    resolved_at: Optional[datetime] = None
    source: str = "rules_engine"
    source_cameras: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    review_status: str = REVIEW_PENDING          # PENDING | CONFIRMED | DISMISSED | INSUFFICIENT_EVIDENCE
    reviewed_by: Optional[str] = None
    reviewed_by_role: Optional[str] = None       # OPERADOR | SUPERVISOR (só quando o revisor foi autenticado)
    reviewer_verified: bool = False              # True = identidade vinda do login; False = nome digitado (modo sem login)
    reviewed_at: Optional[datetime] = None
    review_note: Optional[str] = None
    review_history: list[dict] = field(default_factory=list)   # trilha de auditoria (nunca apagada)
    _processed_eval_ids: set = field(default_factory=set)

    @property
    def key(self) -> str:
        return dedup_key(self.employee_id, self.rule_id, self.ppe_type, self.violation_type.value)

    def duration_seconds(self, now: datetime) -> float:
        end = self.resolved_at if self.resolved_at is not None else now
        return max(0.0, (end - self.opened_at).total_seconds())

    def to_dict(self, now: datetime) -> dict:
        return {
            "incident_id": self.incident_id,
            "employee_id": self.employee_id,
            "evaluation_id": self.first_evaluation_id,
            "last_evaluation_id": self.last_evaluation_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "violation_type": self.violation_type.value,
            "ppe_type": self.ppe_type,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "severity": self.severity.value,
            "status": self.status.value,
            "opened_at": self.opened_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "duration_seconds": round(self.duration_seconds(now), 3),
            "occurrence_count": self.occurrence_count,
            "source": self.source,
            "source_cameras": list(self.source_cameras),
            "metadata": self.metadata,
            "review_status": self.review_status,
            "reviewed_by": self.reviewed_by,
            "reviewed_by_role": self.reviewed_by_role,
            "reviewer_verified": self.reviewer_verified,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_note": self.review_note,
            "review_history": list(self.review_history),
        }

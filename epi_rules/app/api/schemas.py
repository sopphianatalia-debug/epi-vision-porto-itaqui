from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.enums import (
    IndeterminateRollup,
    ObservedStatus,
    Policy,
    Severity,
)
from app.domain.models import (
    EmployeeSafetyStateInput,
    EvaluationContext,
    PPEObservation,
    PPERequirement,
    SafetyRule,
)


# ---------- Avaliação (POST /rules/evaluate) ----------
class PPEIn(BaseModel):
    status: ObservedStatus
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class EvaluateRequest(BaseModel):
    employee_id: Optional[str] = Field(default="FUNC-000234")
    area: Optional[str] = "PATIO_CARGA"
    operation: Optional[str] = "MOVIMENTACAO_CARGA"
    role: Optional[str] = "OPERADOR"
    identity_status: str = "MATCHED"
    timestamp: Optional[datetime] = None
    evaluation_id: Optional[str] = None
    ppe: dict[str, PPEIn] = Field(default_factory=dict)

    def to_input(self) -> EmployeeSafetyStateInput:
        ctx = EvaluationContext(
            employee_id=self.employee_id, area=self.area, operation=self.operation,
            role=self.role, timestamp=self.timestamp, identity_status=self.identity_status,
        )
        ppe = {k: PPEObservation(ObservedStatus(v.status), v.confidence) for k, v in self.ppe.items()}
        return EmployeeSafetyStateInput(context=ctx, ppe=ppe, evaluation_id=self.evaluation_id)


# ---------- CRUD de regras ----------
class RequirementIn(BaseModel):
    ppe_type: str
    required: bool = True
    minimum_confidence: Optional[float] = None
    allowed_statuses: Optional[list[ObservedStatus]] = None
    not_visible_policy: Policy = Policy.INDETERMINATE
    not_observed_policy: Policy = Policy.INDETERMINATE
    unknown_policy: Policy = Policy.INDETERMINATE
    low_confidence_policy: Policy = Policy.INDETERMINATE
    conflicting_policy: Policy = Policy.INDETERMINATE
    severity: Optional[Severity] = None


class RuleIn(BaseModel):
    rule_id: str
    name: str
    description: str = ""
    active: bool = True
    priority: int = 100
    area: Optional[str] = None
    operation: Optional[str] = None
    role: Optional[str] = None
    minimum_confidence: float = 0.85
    severity: Severity = Severity.MEDIUM
    min_violation_seconds: float = 0.0
    min_recovery_seconds: float = 0.0
    indeterminate_rollup: IndeterminateRollup = IndeterminateRollup.INDETERMINATE
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    requirements: list[RequirementIn]

    def to_domain(self, version: int) -> SafetyRule:
        reqs = tuple(
            PPERequirement(
                ppe_type=r.ppe_type, required=r.required, minimum_confidence=r.minimum_confidence,
                allowed_statuses=frozenset(r.allowed_statuses) if r.allowed_statuses else PPERequirement.allowed_statuses,
                not_visible_policy=r.not_visible_policy, not_observed_policy=r.not_observed_policy,
                unknown_policy=r.unknown_policy, low_confidence_policy=r.low_confidence_policy,
                conflicting_policy=r.conflicting_policy, severity=r.severity,
            )
            for r in self.requirements
        )
        return SafetyRule(
            rule_id=self.rule_id, name=self.name, version=version, requirements=reqs,
            description=self.description, active=self.active, priority=self.priority,
            area=self.area, operation=self.operation, role=self.role,
            minimum_confidence=self.minimum_confidence, severity=self.severity,
            min_violation_seconds=self.min_violation_seconds, min_recovery_seconds=self.min_recovery_seconds,
            indeterminate_rollup=self.indeterminate_rollup,
            effective_from=self.effective_from, effective_until=self.effective_until,
        )


def rule_to_dict(rule: SafetyRule) -> dict:
    return {
        "rule_id": rule.rule_id, "name": rule.name, "version": rule.version,
        "active": rule.active, "priority": rule.priority, "area": rule.area,
        "operation": rule.operation, "role": rule.role,
        "minimum_confidence": rule.minimum_confidence, "severity": rule.severity.value,
        "min_violation_seconds": rule.min_violation_seconds,
        "min_recovery_seconds": rule.min_recovery_seconds,
        "indeterminate_rollup": rule.indeterminate_rollup.value,
        "requirements": [
            {"ppe_type": r.ppe_type, "required": r.required,
             "minimum_confidence": r.minimum_confidence,
             "not_visible_policy": r.not_visible_policy.value,
             "unknown_policy": r.unknown_policy.value,
             "severity": r.severity.value if r.severity else None}
            for r in rule.requirements
        ],
    }

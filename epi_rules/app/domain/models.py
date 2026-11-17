"""Entidades e value objects do Rules Engine (tipagem forte)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.enums import (
    DEFAULT_ALLOWED,
    ComplianceStatus,
    IndeterminateRollup,
    ObservedStatus,
    Policy,
    ReasonCode,
    RequirementResult,
    Severity,
)


# --------------------------------------------------------------------------- #
# Configuração de regras (dados, não código)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PPERequirement:
    ppe_type: str
    required: bool = True
    minimum_confidence: Optional[float] = None  # fallback: rule.minimum_confidence
    allowed_statuses: frozenset[ObservedStatus] = frozenset(DEFAULT_ALLOWED)
    not_visible_policy: Policy = Policy.INDETERMINATE
    not_observed_policy: Policy = Policy.INDETERMINATE
    unknown_policy: Policy = Policy.INDETERMINATE
    low_confidence_policy: Policy = Policy.INDETERMINATE
    conflicting_policy: Policy = Policy.INDETERMINATE
    severity: Optional[Severity] = None  # fallback: rule.severity


@dataclass(frozen=True)
class SafetyRule:
    rule_id: str
    name: str
    version: int
    requirements: tuple[PPERequirement, ...]
    description: str = ""
    active: bool = True
    priority: int = 100
    area: Optional[str] = None
    operation: Optional[str] = None
    role: Optional[str] = None
    minimum_confidence: float = 0.85
    severity: Severity = Severity.MEDIUM
    # Debounce / histerese (segundos)
    min_violation_seconds: float = 0.0
    min_recovery_seconds: float = 0.0
    indeterminate_rollup: IndeterminateRollup = IndeterminateRollup.INDETERMINATE
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    created_at: Optional[datetime] = None

    def specificity(self) -> int:
        return sum(x is not None for x in (self.area, self.operation, self.role))

    def is_effective_at(self, when: datetime) -> bool:
        if self.effective_from and when < self.effective_from:
            return False
        if self.effective_until and when > self.effective_until:
            return False
        return True


# --------------------------------------------------------------------------- #
# Entrada
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PPEObservation:
    status: ObservedStatus
    confidence: float = 0.0


@dataclass(frozen=True)
class EvaluationContext:
    employee_id: Optional[str]
    area: Optional[str] = None
    operation: Optional[str] = None
    role: Optional[str] = None
    timestamp: Optional[datetime] = None
    identity_status: str = "MATCHED"
    shift: Optional[str] = None


@dataclass(frozen=True)
class EmployeeSafetyStateInput:
    """Estado consolidado recebido do FusionService (ou payload de debug)."""

    context: EvaluationContext
    ppe: dict[str, PPEObservation]
    evaluation_id: Optional[str] = None  # idempotência


# --------------------------------------------------------------------------- #
# Saída
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RequirementEvaluation:
    ppe_type: str
    required: bool
    observed_status: ObservedStatus
    confidence: float
    minimum_confidence: float
    result: RequirementResult
    reason_code: ReasonCode
    reason: str
    severity: Severity

    def to_dict(self) -> dict:
        return {
            "ppe_type": self.ppe_type,
            "required": self.required,
            "observed_status": self.observed_status.value,
            "confidence": round(self.confidence, 4),
            "minimum_confidence": self.minimum_confidence,
            "result": self.result.value,
            "reason_code": self.reason_code.value,
            "reason": self.reason,
            "severity": self.severity.value,
        }


@dataclass(frozen=True)
class Violation:
    violation_id: str
    rule_id: str
    rule_version: int
    employee_id: Optional[str]
    ppe_type: str
    observed_status: ObservedStatus
    severity: Severity
    confidence: float
    timestamp: datetime
    area: Optional[str]
    operation: Optional[str]
    reason: str

    def to_dict(self) -> dict:
        return {
            "violation_id": self.violation_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "employee_id": self.employee_id,
            "ppe_type": self.ppe_type,
            "observed_status": self.observed_status.value,
            "severity": self.severity.value,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp.isoformat(),
            "area": self.area,
            "operation": self.operation,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    rule_version: int
    status: ComplianceStatus
    requirements: tuple[RequirementEvaluation, ...]
    reason: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "status": self.status.value,
            "requirements": [r.to_dict() for r in self.requirements],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ComplianceEvaluation:
    evaluation_id: str
    employee_id: Optional[str]
    timestamp: datetime
    context: EvaluationContext
    effective_rule_id: Optional[str]
    considered_rule_ids: tuple[str, ...]
    rule_results: tuple[RuleResult, ...]
    overall_status: ComplianceStatus
    violations: tuple[Violation, ...]
    explanation: str

    def to_dict(self) -> dict:
        return {
            "evaluation_id": self.evaluation_id,
            "employee_id": self.employee_id,
            "timestamp": self.timestamp.isoformat(),
            "context": {
                "area": self.context.area,
                "operation": self.context.operation,
                "role": self.context.role,
                "identity_status": self.context.identity_status,
            },
            "effective_rule_id": self.effective_rule_id,
            "considered_rule_ids": list(self.considered_rule_ids),
            "rule_results": [r.to_dict() for r in self.rule_results],
            "overall_status": self.overall_status.value,
            "violations": [v.to_dict() for v in self.violations],
            "explanation": self.explanation,
        }

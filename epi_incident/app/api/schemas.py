from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.domain.enums import OverallStatus, Severity, ViolationType
from app.domain.models import EvaluationInput, ViolationInput




class ViolationIn(BaseModel):
    """Corpo do POST /incidents — uma violação confirmada pelo Rules Engine."""

    employee_id: str = Field(examples=["FUNC-000234"])
    rule_id: str = Field(examples=["RULE-PATIO-CARGA-001"])
    ppe_type: str = Field(examples=["helmet"])
    reason_code: str = Field(examples=["PPE_MISSING"])
    reason: str = Field(default="", examples=["helmet obrigatório e ausente"])
    severity: Severity = Severity.MEDIUM
    rule_version: int = 1
    violation_type: ViolationType = ViolationType.PPE_VIOLATION
    evaluation_id: Optional[str] = Field(default=None, examples=["EVAL-000001"])
    observed_status: Optional[str] = Field(default=None, examples=["MISSING"])
    source_cameras: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    def to_domain(self) -> ViolationInput:
        return ViolationInput(
            employee_id=self.employee_id, rule_id=self.rule_id, ppe_type=self.ppe_type,
            reason_code=self.reason_code, reason=self.reason, severity=self.severity,
            rule_version=self.rule_version, violation_type=self.violation_type,
            evaluation_id=self.evaluation_id, observed_status=self.observed_status,
            source_cameras=tuple(self.source_cameras), metadata=dict(self.metadata),
        )


class RulesViolationIn(BaseModel):
    """Espelha Violation.to_dict() do Rules Engine, com source_cameras opcional
    (o Rules Engine não carrega essa informação; a camada de integração a
    preenche a partir do EmployeeSafetyState do FusionService antes de enviar)."""

    employee_id: Optional[str] = None
    rule_id: str
    rule_version: int = 1
    ppe_type: str
    observed_status: Optional[str] = None
    severity: Severity = Severity.MEDIUM
    reason: str = ""
    reason_code: Optional[str] = None
    source_cameras: list[str] = Field(default_factory=list)


class RulesEvaluationIn(BaseModel):
    """Espelha ComplianceEvaluation.to_dict() do Rules Engine — corpo do
    POST /incidents/evaluations (Fase 3.5, integração ponta-a-ponta)."""

    evaluation_id: Optional[str] = None
    employee_id: Optional[str] = None
    overall_status: OverallStatus
    effective_rule_id: Optional[str] = None
    violations: list[RulesViolationIn] = Field(default_factory=list)

    def to_domain(self) -> EvaluationInput:
        return EvaluationInput(
            employee_id=self.employee_id,
            overall_status=self.overall_status,
            effective_rule_id=self.effective_rule_id,
            evaluation_id=self.evaluation_id,
            violations=tuple(
                ViolationInput(
                    employee_id=v.employee_id or self.employee_id,
                    rule_id=v.rule_id,
                    rule_version=v.rule_version,
                    ppe_type=v.ppe_type,
                    observed_status=v.observed_status,
                    reason_code=v.reason_code or ViolationInput._reason_code_from_status(v.observed_status),
                    reason=v.reason,
                    severity=v.severity,
                    evaluation_id=self.evaluation_id,
                    source_cameras=tuple(v.source_cameras),
                )
                for v in self.violations
            ),
        )


class IncidentOut(BaseModel):
    incident_id: str
    employee_id: str
    evaluation_id: Optional[str]
    last_evaluation_id: Optional[str]
    rule_id: str
    rule_version: int
    violation_type: str
    ppe_type: str
    reason_code: str
    reason: str
    severity: str
    status: str
    opened_at: str
    updated_at: str
    resolved_at: Optional[str]
    duration_seconds: float
    occurrence_count: int
    source: str
    source_cameras: list[str]
    metadata: dict


class CreateIncidentResponse(IncidentOut):
    action: str  # CREATED | UPDATED | NOOP


class EvaluationResultItem(BaseModel):
    action: str
    incident: IncidentOut

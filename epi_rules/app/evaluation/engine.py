"""
RulesEngine — orquestrador da Fase 3.3.

Recebe EmployeeSafetyStateInput (estado consolidado do FusionService), seleciona
a regra efetiva pelo contexto, avalia cada requisito de forma explicável, aplica
debounce/histerese, produz uma ComplianceEvaluation auditável e publica eventos
para o futuro Incident Service. NÃO acessa câmera/YOLO/fusão.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from app.config import Settings
from app.domain.enums import (
    ComplianceStatus,
    EventType,
    IndeterminateRollup,
    ReasonCode,
    RequirementResult,
    RuleState,
)
from app.domain.models import (
    ComplianceEvaluation,
    EmployeeSafetyStateInput,
    RequirementEvaluation,
    RuleResult,
    SafetyRule,
    Violation,
)
from app.evaluation.debounce import DebounceTracker
from app.evaluation.requirement_evaluator import evaluate_requirement
from app.infrastructure import (
    Clock,
    EvaluationRepository,
    EventBus,
    RuleRepository,
    ViolationRepository,
)
from app.observability import log_event, metrics
from app.rules.selection import applicable_rules, resolve_effective


class RulesEngine:
    def __init__(
        self,
        settings: Settings,
        clock: Clock,
        event_bus: EventBus,
        rules: RuleRepository,
        evaluations: EvaluationRepository,
        violations: ViolationRepository,
        debounce: DebounceTracker,
    ) -> None:
        self._s = settings
        self._clock = clock
        self._bus = event_bus
        self._rules = rules
        self._evaluations = evaluations
        self._violations = violations
        self._debounce = debounce

    @property
    def rules(self) -> RuleRepository:
        return self._rules

    @property
    def evaluations(self) -> EvaluationRepository:
        return self._evaluations

    @property
    def violations(self) -> ViolationRepository:
        return self._violations

    @property
    def event_bus(self) -> EventBus:
        return self._bus

    # ------------------------------------------------------------------ #
    def evaluate(self, state: EmployeeSafetyStateInput) -> ComplianceEvaluation:
        start = time.perf_counter()
        now = self._clock.now()
        ctx = state.context
        timestamp = ctx.timestamp or now
        evaluation_id = state.evaluation_id or f"EVAL-{uuid.uuid4().hex[:12]}"

        # Idempotência: mesma avaliação não é reprocessada nem re-emite eventos.
        if state.evaluation_id and self._evaluations.exists(state.evaluation_id):
            return self._evaluations.get(state.evaluation_id)  # type: ignore[return-value]

        # Funcionário não identificado -> não inventar identidade.
        if not ctx.employee_id or ctx.identity_status == "NOT_IDENTIFIED":
            if not self._s.evaluate_anonymous:
                return self._finalize(
                    evaluation_id, state, timestamp, effective=None, considered=(),
                    rule_results=(), overall=ComplianceStatus.NOT_EVALUATED, violations=(),
                    explanation="Funcionário não identificado; avaliação não atribuída.",
                    start=start,
                )

        log_event(EventType.RULE_EVALUATION_STARTED, evaluation_id=evaluation_id,
                  employee_id=ctx.employee_id, area=ctx.area, operation=ctx.operation)

        applicable = applicable_rules(self._rules.all_latest(), ctx, now)
        if not applicable:
            log_event(EventType.RULE_NOT_FOUND, evaluation_id=evaluation_id,
                      area=ctx.area, operation=ctx.operation, role=ctx.role)
            return self._finalize(
                evaluation_id, state, timestamp, effective=None, considered=(),
                rule_results=(), overall=ComplianceStatus.INDETERMINATE, violations=(),
                explanation="Nenhuma regra aplicável ao contexto.", start=start,
            )

        effective = resolve_effective(applicable)
        considered = tuple(r.rule_id for r in applicable)

        rule_result, violations = self._evaluate_rule(effective, state, timestamp)  # type: ignore[arg-type]
        explanation = self._explain(effective, rule_result)  # type: ignore[arg-type]

        return self._finalize(
            evaluation_id, state, timestamp, effective=effective, considered=considered,
            rule_results=(rule_result,), overall=rule_result.status, violations=violations,
            explanation=explanation, start=start,
        )

    # ------------------------------------------------------------------ #
    def _evaluate_rule(
        self, rule: SafetyRule, state: EmployeeSafetyStateInput, timestamp: datetime
    ) -> tuple[RuleResult, tuple[Violation, ...]]:
        ctx = state.context
        evals: list[RequirementEvaluation] = []
        violations: list[Violation] = []

        for req in rule.requirements:
            obs = state.ppe.get(req.ppe_type)
            ev = evaluate_requirement(req, rule, obs)
            evals.append(ev)

            if ev.reason_code == ReasonCode.LOW_CONFIDENCE:
                metrics.record_low_confidence()
                log_event(EventType.LOW_CONFIDENCE_DETECTED, ppe_type=req.ppe_type,
                          confidence=ev.confidence, minimum=ev.minimum_confidence)

            if not req.required:
                continue

            # Debounce/histerese só para requisitos obrigatórios.
            key = (ctx.employee_id or "ANON", rule.rule_id, req.ppe_type)
            stable, became_violation, became_resolved = self._debounce.update(
                key, ev.result, rule.min_violation_seconds, rule.min_recovery_seconds
            )

            if ev.result == RequirementResult.NON_COMPLIANT:
                log_event(EventType.PPE_REQUIREMENT_FAILED, ppe_type=req.ppe_type,
                          rule_id=rule.rule_id, observed=ev.observed_status.value)

            if stable == RuleState.VIOLATION:
                viol = Violation(
                    violation_id=f"VIOL-{state.evaluation_id or 'X'}-{req.ppe_type}"
                    if state.evaluation_id else f"VIOL-{uuid.uuid4().hex[:10]}",
                    rule_id=rule.rule_id, rule_version=rule.version,
                    employee_id=ctx.employee_id, ppe_type=req.ppe_type,
                    observed_status=ev.observed_status, severity=ev.severity,
                    confidence=ev.confidence, timestamp=timestamp,
                    area=ctx.area, operation=ctx.operation, reason=ev.reason,
                )
                violations.append(viol)
                if became_violation:
                    metrics.record_violation_detected()
                    self._bus.publish(EventType.VIOLATION_DETECTED,
                                      {"employee_id": ctx.employee_id, "ppe_type": req.ppe_type,
                                       "rule_id": rule.rule_id, "severity": ev.severity.value})
                    log_event(EventType.VIOLATION_DETECTED, employee_id=ctx.employee_id,
                              ppe_type=req.ppe_type, rule_id=rule.rule_id, severity=ev.severity.value)
            elif became_resolved:
                metrics.record_violation_resolved()
                self._bus.publish(EventType.VIOLATION_RESOLVED,
                                  {"employee_id": ctx.employee_id, "ppe_type": req.ppe_type,
                                   "rule_id": rule.rule_id})
                log_event(EventType.VIOLATION_RESOLVED, employee_id=ctx.employee_id,
                          ppe_type=req.ppe_type, rule_id=rule.rule_id)

        status = self._aggregate(evals, rule.indeterminate_rollup)
        return RuleResult(rule.rule_id, rule.version, status, tuple(evals),
                          f"Regra {rule.rule_id} v{rule.version}: {status.value}"), tuple(violations)

    def _aggregate(self, evals: list[RequirementEvaluation], rollup: IndeterminateRollup) -> ComplianceStatus:
        counting = [e for e in evals if e.result != RequirementResult.NOT_APPLICABLE]
        compliant = sum(e.result == RequirementResult.COMPLIANT for e in counting)
        non_compliant = sum(e.result == RequirementResult.NON_COMPLIANT for e in counting)
        indeterminate = sum(e.result == RequirementResult.INDETERMINATE for e in counting)

        if non_compliant > 0:
            return ComplianceStatus.NON_COMPLIANT
        if indeterminate == 0:
            return ComplianceStatus.COMPLIANT  # inclui o caso "só opcionais"
        if compliant > 0:
            return (ComplianceStatus.PARTIAL if rollup == IndeterminateRollup.PARTIAL
                    else ComplianceStatus.INDETERMINATE)
        return ComplianceStatus.INDETERMINATE

    def _explain(self, rule: SafetyRule, result: RuleResult) -> str:
        parts = [f"{result.status.value} pela regra {rule.rule_id} v{rule.version}."]
        for e in result.requirements:
            if e.result != RequirementResult.COMPLIANT and e.result != RequirementResult.NOT_APPLICABLE:
                parts.append(f"{e.ppe_type}: {e.result.value} ({e.reason}).")
        return " ".join(parts)

    # ------------------------------------------------------------------ #
    def _finalize(self, evaluation_id, state, timestamp, effective, considered,
                  rule_results, overall, violations, explanation, start) -> ComplianceEvaluation:
        ctx = state.context
        evaluation = ComplianceEvaluation(
            evaluation_id=evaluation_id, employee_id=ctx.employee_id, timestamp=timestamp,
            context=ctx, effective_rule_id=effective.rule_id if effective else None,
            considered_rule_ids=considered, rule_results=rule_results,
            overall_status=overall, violations=violations, explanation=explanation,
        )

        # Mudança de status de conformidade (para o Incident Service).
        previous = self._evaluations.latest_for_employee(ctx.employee_id) if ctx.employee_id else None
        self._evaluations.save(evaluation)
        for v in violations:
            self._violations.add(v)

        if previous is not None and previous.overall_status != overall:
            self._bus.publish(EventType.COMPLIANCE_STATUS_CHANGED,
                              {"employee_id": ctx.employee_id,
                               "from": previous.overall_status.value, "to": overall.value})
            log_event(EventType.COMPLIANCE_STATUS_CHANGED, employee_id=ctx.employee_id,
                      **{"from": previous.overall_status.value, "to": overall.value})

        if overall in (ComplianceStatus.INDETERMINATE, ComplianceStatus.PARTIAL):
            self._bus.publish(EventType.EVALUATION_INDETERMINATE,
                              {"employee_id": ctx.employee_id, "status": overall.value})

        latency_ms = (time.perf_counter() - start) * 1000.0
        metrics.record_evaluation(overall, latency_ms, ctx.area, ctx.operation, ctx.role)
        self._bus.publish(EventType.RULE_EVALUATED,
                          {"evaluation_id": evaluation_id, "employee_id": ctx.employee_id,
                           "overall": overall.value})
        log_event(EventType.RULE_EVALUATED, evaluation_id=evaluation_id,
                  employee_id=ctx.employee_id, overall=overall.value,
                  rule_id=effective.rule_id if effective else None,
                  rule_version=effective.version if effective else None,
                  latency_ms=round(latency_ms, 3))
        return evaluation

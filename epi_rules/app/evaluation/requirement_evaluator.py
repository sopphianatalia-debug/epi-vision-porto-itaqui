"""
Avaliação de UM requisito de EPI.

Traduz (status observado + confiança + políticas da regra) em um resultado
explicável. NÃO é if/else espalhado: cada status tem um caminho claro e cada
decisão carrega reason_code + texto para auditoria.
"""
from __future__ import annotations

from app.domain.enums import (
    ObservedStatus,
    Policy,
    ReasonCode,
    RequirementResult,
    Severity,
)
from app.domain.models import (
    PPEObservation,
    PPERequirement,
    RequirementEvaluation,
    SafetyRule,
)

_PRESENCE = {ObservedStatus.DETECTED, ObservedStatus.PROPER, ObservedStatus.PRESENT, ObservedStatus.IMPROPER}


def _policy_result(policy: Policy) -> RequirementResult:
    return {
        Policy.INDETERMINATE: RequirementResult.INDETERMINATE,
        Policy.NON_COMPLIANT: RequirementResult.NON_COMPLIANT,
        Policy.COMPLIANT: RequirementResult.COMPLIANT,
        Policy.IGNORE: RequirementResult.NOT_APPLICABLE,
    }[policy]


def evaluate_requirement(
    req: PPERequirement, rule: SafetyRule, obs: PPEObservation | None
) -> RequirementEvaluation:
    status = obs.status if obs else ObservedStatus.NOT_OBSERVED
    confidence = obs.confidence if obs else 0.0
    min_conf = req.minimum_confidence if req.minimum_confidence is not None else rule.minimum_confidence
    severity = req.severity or rule.severity

    def build(result: RequirementResult, code: ReasonCode, reason: str) -> RequirementEvaluation:
        return RequirementEvaluation(
            ppe_type=req.ppe_type, required=req.required, observed_status=status,
            confidence=confidence, minimum_confidence=min_conf, result=result,
            reason_code=code, reason=reason, severity=severity,
        )

    # --- EPI opcional: nunca vira violação ---
    if not req.required:
        if status in req.allowed_statuses:
            return build(RequirementResult.COMPLIANT, ReasonCode.OK,
                         f"{req.ppe_type} opcional presente ({status.value})")
        return build(RequirementResult.NOT_APPLICABLE, ReasonCode.OPTIONAL_ABSENT,
                     f"{req.ppe_type} é opcional e não foi detectado")

    # --- presença (status permitido) -> gating por confiança ---
    if status in req.allowed_statuses:
        if confidence >= min_conf:
            return build(RequirementResult.COMPLIANT, ReasonCode.OK,
                         f"{req.ppe_type}={status.value} com confiança {confidence:.2f} ≥ {min_conf:.2f}")
        result = _policy_result(req.low_confidence_policy)
        return build(result, ReasonCode.LOW_CONFIDENCE,
                     f"{req.ppe_type}={status.value} mas confiança {confidence:.2f} < {min_conf:.2f} "
                     f"(política LOW_CONFIDENCE={req.low_confidence_policy.value})")

    # --- status específicos ---
    if status == ObservedStatus.IMPROPER:
        return build(RequirementResult.NON_COMPLIANT, ReasonCode.IMPROPER,
                     f"{req.ppe_type} presente porém usado incorretamente (IMPROPER)")
    if status == ObservedStatus.MISSING:
        return build(RequirementResult.NON_COMPLIANT, ReasonCode.MISSING,
                     f"{req.ppe_type} obrigatório e ausente (MISSING)")
    if status == ObservedStatus.NOT_VISIBLE:
        return build(_policy_result(req.not_visible_policy), ReasonCode.NOT_VISIBLE,
                     f"{req.ppe_type} não verificável (NOT_VISIBLE); política={req.not_visible_policy.value}")
    if status == ObservedStatus.NOT_OBSERVED:
        return build(_policy_result(req.not_observed_policy), ReasonCode.NOT_OBSERVED,
                     f"{req.ppe_type} sem observação (NOT_OBSERVED); política={req.not_observed_policy.value}")
    if status == ObservedStatus.CONFLICTING:
        return build(_policy_result(req.conflicting_policy), ReasonCode.CONFLICTING,
                     f"{req.ppe_type} com evidências conflitantes (CONFLICTING); política={req.conflicting_policy.value}")
    if status == ObservedStatus.LOW_CONFIDENCE:
        return build(_policy_result(req.low_confidence_policy), ReasonCode.LOW_CONFIDENCE,
                     f"{req.ppe_type} com baixa confiança; política={req.low_confidence_policy.value}")

    # UNKNOWN e qualquer outro
    return build(_policy_result(req.unknown_policy), ReasonCode.UNKNOWN,
                 f"{req.ppe_type} com status indeterminado ({status.value}); política={req.unknown_policy.value}")

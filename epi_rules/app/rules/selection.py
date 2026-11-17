"""
Seleção de regras aplicáveis a um contexto e resolução determinística.

Uma regra é aplicável se estiver ativa, vigente (effective_from/until) e casar
com o contexto: cada dimensão declarada (area/operation/role) precisa bater; uma
dimensão não declarada (None) é curinga.

Resolução (regra específica sobrescreve genérica), em ordem:
1. maior especificidade (mais dimensões declaradas);
2. maior prioridade;
3. maior versão.
"""
from __future__ import annotations

from datetime import datetime

from app.domain.models import EvaluationContext, SafetyRule


def _matches(rule: SafetyRule, ctx: EvaluationContext) -> bool:
    if rule.area is not None and rule.area != ctx.area:
        return False
    if rule.operation is not None and rule.operation != ctx.operation:
        return False
    if rule.role is not None and rule.role != ctx.role:
        return False
    return True


def applicable_rules(rules: list[SafetyRule], ctx: EvaluationContext, when: datetime) -> list[SafetyRule]:
    return [
        r for r in rules
        if r.active and r.is_effective_at(when) and _matches(r, ctx)
    ]


def resolve_effective(rules: list[SafetyRule]) -> SafetyRule | None:
    if not rules:
        return None
    return sorted(
        rules,
        key=lambda r: (r.specificity(), r.priority, r.version),
        reverse=True,
    )[0]

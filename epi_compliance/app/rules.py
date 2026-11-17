"""
Motor de regras de conformidade (seção 13 do spec).

Combina os status finais dos EPIs exigidos em um veredito geral:
- violação  = MISSING ou IMPROPER (região visível, EPI ausente/mal usado);
- indefinido = NOT_VISIBLE ou UNKNOWN (não dá para afirmar);
- ok        = PROPER (ou PRESENT).

Regras:
- sem violação e sem indefinido            -> COMPLIANT
- sem violação, mas com indefinido         -> UNDETERMINED
- com violação e algum OK                   -> PARTIAL_NON_COMPLIANCE
- com violação e nenhum OK                   -> NON_COMPLIANT
"""
from __future__ import annotations

from app.enums import ComplianceStatus, PPEStatus
from app.types import ComplianceResult, PPEResult

_VIOLATION = {PPEStatus.MISSING, PPEStatus.IMPROPER}
_OK = {PPEStatus.PROPER, PPEStatus.PRESENT}
_INDETERMINATE = {PPEStatus.NOT_VISIBLE, PPEStatus.UNKNOWN}


def _combined_gloves(left: PPEResult, right: PPEResult) -> PPEStatus:
    """Status único de 'gloves' a partir das duas mãos."""
    both = [left.status, right.status]
    if all(s in _INDETERMINATE for s in both):
        return PPEStatus.NOT_VISIBLE
    # Se qualquer mão visível está sem luva -> violação.
    if any(s in _VIOLATION for s in both):
        return PPEStatus.MISSING
    if all(s in _OK or s in _INDETERMINATE for s in both):
        return PPEStatus.PROPER
    return PPEStatus.UNKNOWN


class ComplianceRulesEngine:
    def __init__(self, required_ppe: list[str]) -> None:
        self.required = set(required_ppe)

    def _status_for(self, key: str, result: ComplianceResult) -> PPEStatus:
        if key == "gloves":
            return _combined_gloves(result.glove_left, result.glove_right)
        return getattr(result, key).status

    def evaluate(self, result: ComplianceResult) -> ComplianceStatus:
        violations = ok = indeterminate = 0
        for key in self.required:
            status = self._status_for(key, result)
            if status in _VIOLATION:
                violations += 1
            elif status in _OK:
                ok += 1
            else:
                indeterminate += 1

        if violations == 0:
            return ComplianceStatus.COMPLIANT if indeterminate == 0 else ComplianceStatus.UNDETERMINED
        return (
            ComplianceStatus.PARTIAL_NON_COMPLIANCE if ok > 0 else ComplianceStatus.NON_COMPLIANT
        )

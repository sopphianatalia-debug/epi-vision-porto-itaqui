"""
Regras de exemplo (seed) — dados, não código.

Demonstram regras por área/operação/função e a sobreposição específico > genérico.
Em produção, viriam de um banco/config externo via RuleRepository.
"""
from __future__ import annotations

from app.domain.enums import Policy, Severity
from app.domain.models import PPERequirement, SafetyRule


def _req(ppe: str, required: bool = True, severity: Severity | None = None,
         min_conf: float | None = None) -> PPERequirement:
    return PPERequirement(ppe_type=ppe, required=required, severity=severity, minimum_confidence=min_conf)


SEED_RULES: list[SafetyRule] = [
    SafetyRule(
        rule_id="RULE-PATIO-CARGA-001",
        name="EPIs obrigatórios para movimentação de carga",
        version=1,
        area="PATIO_CARGA",
        operation="MOVIMENTACAO_CARGA",
        priority=100,
        minimum_confidence=0.85,
        severity=Severity.HIGH,
        min_violation_seconds=0.0,   # cenários avaliam um estado por vez
        min_recovery_seconds=0.0,
        requirements=(
            _req("helmet", severity=Severity.CRITICAL),
            _req("vest", severity=Severity.HIGH),
            _req("gloves", severity=Severity.MEDIUM),
            _req("boots", severity=Severity.MEDIUM),
        ),
    ),
    SafetyRule(
        rule_id="RULE-INSPECAO-001",
        name="EPIs para inspeção",
        version=1,
        operation="INSPECAO",
        priority=90,
        severity=Severity.MEDIUM,
        requirements=(
            _req("helmet", severity=Severity.CRITICAL),
            _req("vest", severity=Severity.HIGH),
            _req("boots", severity=Severity.MEDIUM),
            _req("gloves", required=False),
        ),
    ),
    SafetyRule(
        rule_id="RULE-MANUTENCAO-001",
        name="EPIs para manutenção",
        version=1,
        operation="MANUTENCAO",
        priority=90,
        severity=Severity.HIGH,
        requirements=(
            _req("helmet", severity=Severity.CRITICAL),
            _req("vest", severity=Severity.HIGH),
            _req("gloves", severity=Severity.MEDIUM),
            _req("boots", severity=Severity.MEDIUM),
            _req("glasses", severity=Severity.MEDIUM),
        ),
    ),
    # Regra genérica de fallback por área (menos específica).
    SafetyRule(
        rule_id="RULE-PATIO-GERAL-001",
        name="EPIs gerais no pátio",
        version=1,
        area="PATIO_CARGA",
        priority=50,
        severity=Severity.MEDIUM,
        requirements=(
            _req("helmet", severity=Severity.CRITICAL),
            _req("vest", severity=Severity.HIGH),
        ),
    ),
]

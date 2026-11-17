from app.domain.enums import ComplianceStatus, Severity
from app.infrastructure import RuleRepository
from tests.conftest import make_engine, make_settings, req, rule, state


def _engine_with(*rules):
    repo = RuleRepository()
    for r in rules:
        repo.save(r)
    return make_engine(settings=make_settings(load_seed_rules=False), rules=repo)


def test_specific_rule_overrides_generic():
    generic = rule("R-GEN", [req("helmet")], area="PATIO_CARGA", priority=50)
    specific = rule("R-SPEC", [req("helmet"), req("gloves")],
                    area="PATIO_CARGA", operation="MOVIMENTACAO_CARGA", role="OPERADOR", priority=50)
    eng, _c, _b = _engine_with(generic, specific)
    r = eng.evaluate(state({"helmet": ("DETECTED", 0.95), "gloves": ("MISSING", 0.9)}))
    assert r.effective_rule_id == "R-SPEC"           # mais específica vence
    assert r.overall_status == ComplianceStatus.NON_COMPLIANT


def test_priority_breaks_tie_same_specificity():
    low = rule("R-LOW", [req("helmet")], area="PATIO_CARGA", priority=10)
    high = rule("R-HIGH", [req("helmet"), req("boots")], area="PATIO_CARGA", priority=99)
    eng, _c, _b = _engine_with(low, high)
    r = eng.evaluate(state({"helmet": ("DETECTED", 0.95), "boots": ("DETECTED", 0.95)}))
    assert r.effective_rule_id == "R-HIGH"


def test_different_area_not_applicable():
    r_area_a = rule("R-A", [req("helmet")], area="AREA_A")
    eng, _c, _b = _engine_with(r_area_a)
    r = eng.evaluate(state({"helmet": ("DETECTED", 0.95)}, area="AREA_B"))
    assert r.overall_status == ComplianceStatus.INDETERMINATE   # nenhuma regra aplicável
    assert r.effective_rule_id is None


def test_different_operation_selects_right_rule():
    op1 = rule("R-OP1", [req("helmet")], operation="INSPECAO")
    op2 = rule("R-OP2", [req("helmet"), req("glasses")], operation="MANUTENCAO")
    eng, _c, _b = _engine_with(op1, op2)
    r = eng.evaluate(state({"helmet": ("DETECTED", 0.95)}, operation="INSPECAO"))
    assert r.effective_rule_id == "R-OP1"


def test_role_influences_rule():
    r_role = rule("R-ROLE", [req("helmet"), req("gloves")], role="TECNICO_MANUTENCAO")
    eng, _c, _b = _engine_with(r_role)
    r_match = eng.evaluate(state({"helmet": ("DETECTED", 0.95), "gloves": ("DETECTED", 0.95)},
                                 role="TECNICO_MANUTENCAO"))
    assert r_match.effective_rule_id == "R-ROLE"
    r_other = eng.evaluate(state({"helmet": ("DETECTED", 0.95)}, role="SUPERVISOR"))
    assert r_other.effective_rule_id is None


def test_inactive_rule_is_ignored():
    inactive = rule("R-OFF", [req("helmet")], area="AREA_X", active=False)
    eng, _c, _b = _engine_with(inactive)
    r = eng.evaluate(state({"helmet": ("DETECTED", 0.95)}, area="AREA_X"))
    assert r.effective_rule_id is None


def test_expired_rule_is_ignored():
    from datetime import datetime, timezone
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    expired = rule("R-EXP", [req("helmet")], area="AREA_X",
                   effective_until=past)
    eng, _c, _b = _engine_with(expired)
    r = eng.evaluate(state({"helmet": ("DETECTED", 0.95)}, area="AREA_X"))
    assert r.effective_rule_id is None


def test_versioning_latest_wins_and_history_kept():
    repo = RuleRepository()
    repo.save(rule("R-V", [req("helmet")], area="AREA_X", version=1))
    repo.save(rule("R-V", [req("helmet"), req("gloves")], area="AREA_X", version=2))
    eng, _c, _b = make_engine(settings=make_settings(load_seed_rules=False), rules=repo)
    r = eng.evaluate(state({"helmet": ("DETECTED", 0.95), "gloves": ("MISSING", 0.9)}, area="AREA_X"))
    assert r.rule_results[0].rule_version == 2
    assert r.overall_status == ComplianceStatus.NON_COMPLIANT
    # histórico preservado
    assert repo.get_version("R-V", 1) is not None
    assert len(repo.versions("R-V")) == 2

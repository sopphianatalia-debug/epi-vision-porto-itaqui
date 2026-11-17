from app.domain.enums import ComplianceStatus, ObservedStatus, Policy, Severity
from tests.conftest import make_engine, make_settings, req, rule, state


def custom_engine(requirements, **rule_kw):
    from app.infrastructure import RuleRepository
    repo = RuleRepository()
    repo.save(rule("RULE-TEST", requirements, area="AREA_T", operation="OP_T", role="ROLE_T", **rule_kw))
    return make_engine(settings=make_settings(load_seed_rules=False), rules=repo)


def st(ppe, **kw):
    return state(ppe, area="AREA_T", operation="OP_T", role="ROLE_T", **kw)


def test_all_required_present_is_compliant():
    eng, _c, _b = custom_engine([req("helmet"), req("vest")])
    r = eng.evaluate(st({"helmet": ("DETECTED", 0.95), "vest": ("DETECTED", 0.95)}))
    assert r.overall_status == ComplianceStatus.COMPLIANT


def test_one_required_missing_is_non_compliant():
    eng, _c, _b = custom_engine([req("helmet"), req("vest")])
    r = eng.evaluate(st({"helmet": ("DETECTED", 0.95), "vest": ("MISSING", 0.9)}))
    assert r.overall_status == ComplianceStatus.NON_COMPLIANT
    assert [v.ppe_type for v in r.violations] == ["vest"]


def test_multiple_missing():
    eng, _c, _b = custom_engine([req("helmet"), req("vest"), req("boots")])
    r = eng.evaluate(st({"helmet": ("MISSING", 0.9), "vest": ("MISSING", 0.9), "boots": ("DETECTED", 0.9)}))
    assert r.overall_status == ComplianceStatus.NON_COMPLIANT
    assert len(r.violations) == 2


def test_optional_absent_is_not_violation():
    eng, _c, _b = custom_engine([req("helmet"), req("glasses", required=False)])
    r = eng.evaluate(st({"helmet": ("DETECTED", 0.95)}))
    assert r.overall_status == ComplianceStatus.COMPLIANT
    assert not r.violations


def test_not_visible_is_indeterminate_not_missing():
    eng, _c, _b = custom_engine([req("helmet"), req("boots")])
    r = eng.evaluate(st({"helmet": ("DETECTED", 0.95), "boots": ("NOT_VISIBLE", 0.0)}))
    assert r.overall_status == ComplianceStatus.INDETERMINATE
    assert not r.violations  # nunca vira violação por não ser visível


def test_not_observed_is_indeterminate():
    eng, _c, _b = custom_engine([req("helmet"), req("boots")])
    r = eng.evaluate(st({"helmet": ("DETECTED", 0.95), "boots": ("NOT_OBSERVED", 0.0)}))
    assert r.overall_status == ComplianceStatus.INDETERMINATE


def test_unknown_is_indeterminate():
    eng, _c, _b = custom_engine([req("helmet")])
    r = eng.evaluate(st({"helmet": ("UNKNOWN", 0.0)}))
    assert r.overall_status == ComplianceStatus.INDETERMINATE


def test_conflicting_is_indeterminate_by_default():
    eng, _c, _b = custom_engine([req("helmet")])
    r = eng.evaluate(st({"helmet": ("CONFLICTING", 0.0)}))
    assert r.overall_status == ComplianceStatus.INDETERMINATE


def test_confidence_above_threshold_is_compliant():
    eng, _c, _b = custom_engine([req("helmet", minimum_confidence=0.85)])
    r = eng.evaluate(st({"helmet": ("DETECTED", 0.9)}))
    assert r.overall_status == ComplianceStatus.COMPLIANT


def test_confidence_below_threshold_is_indeterminate():
    eng, _c, _b = custom_engine([req("helmet", minimum_confidence=0.85)])
    r = eng.evaluate(st({"helmet": ("DETECTED", 0.55)}))
    assert r.overall_status == ComplianceStatus.INDETERMINATE
    assert r.rule_results[0].requirements[0].reason_code.value == "LOW_CONFIDENCE"


def test_low_confidence_policy_non_compliant():
    eng, _c, _b = custom_engine([req("helmet", minimum_confidence=0.85,
                                     low_confidence_policy=Policy.NON_COMPLIANT)])
    r = eng.evaluate(st({"helmet": ("DETECTED", 0.5)}))
    assert r.overall_status == ComplianceStatus.NON_COMPLIANT


def test_not_visible_policy_can_be_non_compliant():
    eng, _c, _b = custom_engine([req("boots", not_visible_policy=Policy.NON_COMPLIANT)])
    r = eng.evaluate(st({"boots": ("NOT_VISIBLE", 0.0)}))
    assert r.overall_status == ComplianceStatus.NON_COMPLIANT


def test_severity_comes_from_requirement():
    eng, _c, _b = custom_engine([req("helmet", severity=Severity.CRITICAL)])
    r = eng.evaluate(st({"helmet": ("MISSING", 0.9)}))
    assert r.violations[0].severity == Severity.CRITICAL


def test_explainability_present():
    eng, _c, _b = custom_engine([req("gloves")])
    r = eng.evaluate(st({"gloves": ("MISSING", 0.94)}))
    assert "gloves" in r.explanation
    assert r.rule_results[0].requirements[0].reason  # texto explicável

from app.domain.enums import ComplianceStatus
from tests.conftest import make_engine, state


def _eng():
    eng, _c, _b = make_engine()  # com regras seed
    return eng


def test_cenario_1_conforme():
    r = _eng().evaluate(state({
        "helmet": ("DETECTED", 0.98), "vest": ("DETECTED", 0.97),
        "gloves": ("DETECTED", 0.95), "boots": ("DETECTED", 0.96),
    }))
    assert r.overall_status == ComplianceStatus.COMPLIANT
    assert not r.violations


def test_cenario_2_nao_conforme_gloves():
    r = _eng().evaluate(state({
        "helmet": ("DETECTED", 0.98), "vest": ("DETECTED", 0.97),
        "gloves": ("MISSING", 0.93), "boots": ("DETECTED", 0.96),
    }))
    assert r.overall_status == ComplianceStatus.NON_COMPLIANT
    assert [v.ppe_type for v in r.violations] == ["gloves"]


def test_cenario_3_nao_visivel_indeterminate():
    r = _eng().evaluate(state({
        "helmet": ("DETECTED", 0.98), "vest": ("DETECTED", 0.97),
        "gloves": ("NOT_VISIBLE", 0.0), "boots": ("DETECTED", 0.96),
    }))
    assert r.overall_status == ComplianceStatus.INDETERMINATE
    assert not r.violations  # NOT_VISIBLE nunca vira MISSING


def test_cenario_4_baixa_confianca():
    r = _eng().evaluate(state({
        "helmet": ("DETECTED", 0.55), "vest": ("DETECTED", 0.97),
        "gloves": ("DETECTED", 0.95), "boots": ("DETECTED", 0.96),
    }))
    assert r.overall_status == ComplianceStatus.INDETERMINATE
    helmet = next(e for e in r.rule_results[0].requirements if e.ppe_type == "helmet")
    assert helmet.reason_code.value == "LOW_CONFIDENCE"


def test_cenario_5_conflito():
    r = _eng().evaluate(state({
        "helmet": ("CONFLICTING", 0.0), "vest": ("DETECTED", 0.97),
        "gloves": ("DETECTED", 0.95), "boots": ("DETECTED", 0.96),
    }))
    assert r.overall_status == ComplianceStatus.INDETERMINATE


def test_cenario_6_nao_identificado():
    r = _eng().evaluate(state({"helmet": ("DETECTED", 0.9)}, employee=None, identity="NOT_IDENTIFIED"))
    assert r.overall_status == ComplianceStatus.NOT_EVALUATED
    assert r.employee_id is None

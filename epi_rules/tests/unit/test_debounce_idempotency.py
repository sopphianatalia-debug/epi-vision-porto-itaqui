from app.domain.enums import ComplianceStatus, RuleState
from app.infrastructure import RuleRepository
from tests.conftest import make_engine, make_settings, req, rule, state


def _debounced_engine(min_violation=2.0, min_recovery=2.0):
    repo = RuleRepository()
    repo.save(rule("R-DB", [req("helmet")], area="AREA_D",
                   min_violation_seconds=min_violation, min_recovery_seconds=min_recovery))
    return make_engine(settings=make_settings(load_seed_rules=False), rules=repo)


def st(ppe):
    return state(ppe, area="AREA_D", operation=None, role=None)


def test_violation_pending_within_debounce_window():
    eng, clock, _b = _debounced_engine(min_violation=2.0)
    r = eng.evaluate(st({"helmet": ("MISSING", 0.9)}))
    # instantaneamente NON_COMPLIANT, mas violação ainda não confirmada
    assert r.overall_status == ComplianceStatus.NON_COMPLIANT
    assert not r.violations  # dentro da janela -> PENDING, sem violação definitiva


def test_violation_confirmed_after_debounce():
    eng, clock, bus = _debounced_engine(min_violation=2.0)
    eng.evaluate(st({"helmet": ("MISSING", 0.9)}))     # t=0 PENDING
    clock.advance(3.0)
    r = eng.evaluate(st({"helmet": ("MISSING", 0.9)}))  # t=3 -> confirma
    assert len(r.violations) == 1
    assert any(e["type"] == "VIOLATION_DETECTED" for e in bus.recent())


def test_recovery_requires_hysteresis():
    eng, clock, bus = _debounced_engine(min_violation=0.0, min_recovery=2.0)
    eng.evaluate(st({"helmet": ("MISSING", 0.9)}))       # violação imediata
    clock.advance(0.5)
    r = eng.evaluate(st({"helmet": ("DETECTED", 0.95)}))  # recuperou há pouco
    # ainda não passou a histerese -> continua em violação
    assert len(r.violations) == 1
    clock.advance(3.0)
    r2 = eng.evaluate(st({"helmet": ("DETECTED", 0.95)}))
    assert not r2.violations
    assert any(e["type"] == "VIOLATION_RESOLVED" for e in bus.recent())


def test_oscillation_does_not_flap():
    eng, clock, bus = _debounced_engine(min_violation=2.0, min_recovery=2.0)
    # alterna rápido: nunca fica 2s contínuos em nenhum estado
    for status in ["MISSING", "DETECTED", "MISSING", "DETECTED"]:
        clock.advance(0.3)
        r = eng.evaluate(st({"helmet": (status, 0.9)}))
    detected = [e for e in bus.recent() if e["type"] == "VIOLATION_DETECTED"]
    assert not detected  # sem ocorrência aberta por ruído de frame


def test_idempotent_same_evaluation_id():
    eng, _c, bus = _debounced_engine(min_violation=0.0)
    s = st({"helmet": ("MISSING", 0.9)})
    from app.domain.models import EmployeeSafetyStateInput
    s = EmployeeSafetyStateInput(context=s.context, ppe=s.ppe, evaluation_id="EVAL-FIXED-1")
    r1 = eng.evaluate(s)
    r2 = eng.evaluate(s)  # idêntico -> não reprocessa
    assert r1.evaluation_id == r2.evaluation_id == "EVAL-FIXED-1"
    detected = [e for e in bus.recent() if e["type"] == "VIOLATION_DETECTED"]
    assert len(detected) == 1  # não duplicou

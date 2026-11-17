from app.domain.enums import Action, EventType
from tests.conftest import make_service, viol


def test_idempotent_same_evaluation_id():
    svc, _c, bus = make_service()
    svc.record_violation(viol(evaluation_id="EVAL-SAME"))
    inc, action = svc.record_violation(viol(evaluation_id="EVAL-SAME"))
    assert action == Action.NOOP
    assert inc.occurrence_count == 1                 # não incrementa
    assert bus.count(EventType.INCIDENT_CREATED) == 1
    assert bus.count(EventType.INCIDENT_UPDATED) == 0  # NOOP não emite


def test_distinct_evaluations_increment_occurrence():
    svc, _c, _b = make_service()
    svc.record_violation(viol(evaluation_id="E1"))
    svc.record_violation(viol(evaluation_id="E2"))
    svc.record_violation(viol(evaluation_id="E3"))
    assert svc.list()[0].occurrence_count == 3


def test_dedup_key_ignores_camera():
    svc, _c, _b = make_service()
    svc.record_violation(viol(evaluation_id="E1", cameras=["CAM-01"]))
    inc, action = svc.record_violation(viol(evaluation_id="E2", cameras=["CAM-02"]))
    assert action == Action.UPDATED   # mesma chave lógica, câmera diferente
    assert len(svc.list()) == 1


def test_dedup_separates_by_rule():
    svc, _c, _b = make_service()
    svc.record_violation(viol(rule="RULE-A", evaluation_id="E1"))
    svc.record_violation(viol(rule="RULE-B", evaluation_id="E1"))
    assert len(svc.list()) == 2   # regras diferentes -> incidentes diferentes


def test_reprocessing_same_event_twice_no_duplicate():
    svc, _c, _b = make_service()
    v = viol(evaluation_id="EVAL-X")
    svc.record_violation(v)
    svc.record_violation(v)  # reentrega do MESMO evento
    assert len(svc.list()) == 1
    assert svc.list()[0].occurrence_count == 1

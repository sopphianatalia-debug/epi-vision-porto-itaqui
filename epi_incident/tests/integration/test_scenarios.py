from app.domain.enums import IncidentStatus
from tests.conftest import evaluation, make_service, viol


def test_c1_violacao_simples():
    svc, _c, _b = make_service()
    svc.process_evaluation(evaluation(
        status="NON_COMPLIANT", evaluation_id="E1",
        violations=[viol(ppe="helmet", evaluation_id="E1")]))
    incs = svc.list()
    assert len(incs) == 1 and incs[0].status == IncidentStatus.OPEN


def test_c2_violacao_persistente_10x():
    svc, _c, _b = make_service()
    for i in range(10):
        svc.process_evaluation(evaluation(
            status="NON_COMPLIANT", evaluation_id=f"E{i}",
            violations=[viol(ppe="helmet", evaluation_id=f"E{i}")]))
    incs = svc.list()
    assert len(incs) == 1
    assert incs[0].occurrence_count == 10


def test_c3_resolucao():
    svc, clock, _b = make_service()
    svc.process_evaluation(evaluation(
        status="NON_COMPLIANT", evaluation_id="E1",
        violations=[viol(evaluation_id="E1")]))
    clock.advance(15.0)
    svc.process_evaluation(evaluation(status="COMPLIANT", evaluation_id="E2", violations=[]))
    inc = svc.list()[0]
    assert inc.status == IncidentStatus.RESOLVED
    assert inc.resolved_at is not None
    assert inc.duration_seconds(clock.now()) == 15.0


def test_c4_reincidencia():
    svc, clock, _b = make_service()
    svc.process_evaluation(evaluation(status="NON_COMPLIANT", evaluation_id="E1",
                                      violations=[viol(evaluation_id="E1")]))
    clock.advance(10.0)
    svc.process_evaluation(evaluation(status="COMPLIANT", evaluation_id="E2", violations=[]))
    clock.advance(20.0)
    svc.process_evaluation(evaluation(status="NON_COMPLIANT", evaluation_id="E3",
                                      violations=[viol(evaluation_id="E3")]))
    ids = {i.incident_id: i.status for i in svc.list()}
    assert ids["INC-000001"] == IncidentStatus.RESOLVED
    assert ids["INC-000002"] == IncidentStatus.OPEN


def test_c5_indeterminate_no_incident():
    svc, _c, _b = make_service()
    svc.process_evaluation(evaluation(status="INDETERMINATE", evaluation_id="E1", violations=[]))
    assert svc.list() == []


def test_c6_low_confidence_no_incident():
    # LOW_CONFIDENCE é tratado pelo Rules Engine como INDETERMINATE (sem violação).
    svc, _c, _b = make_service()
    svc.process_evaluation(evaluation(status="INDETERMINATE", evaluation_id="E1", violations=[]))
    assert svc.list() == []


def test_c7_conflicting_no_incident():
    svc, _c, _b = make_service()
    svc.process_evaluation(evaluation(status="CONFLICTING", evaluation_id="E1", violations=[]))
    assert svc.list() == []


def test_c8_dois_epis():
    svc, _c, _b = make_service()
    svc.process_evaluation(evaluation(
        status="NON_COMPLIANT", evaluation_id="E1",
        violations=[viol(ppe="helmet", evaluation_id="E1"), viol(ppe="gloves", evaluation_id="E1")]))
    assert sorted(i.ppe_type for i in svc.list()) == ["gloves", "helmet"]
    assert len(svc.list()) == 2


def test_c9_duas_cameras_um_incidente():
    svc, _c, _b = make_service()
    # Mesma condição, câmeras distintas (em avaliações distintas) -> 1 incidente.
    svc.process_evaluation(evaluation(status="NON_COMPLIANT", evaluation_id="E1",
                                      violations=[viol(evaluation_id="E1", cameras=["CAM-01"])]))
    svc.process_evaluation(evaluation(status="NON_COMPLIANT", evaluation_id="E2",
                                      violations=[viol(evaluation_id="E2", cameras=["CAM-02"])]))
    assert len(svc.list()) == 1


def test_c10_funcionarios_diferentes():
    svc, _c, _b = make_service()
    svc.process_evaluation(evaluation(employee="FUNC-001", status="NON_COMPLIANT", evaluation_id="E1",
                                      violations=[viol(employee="FUNC-001", evaluation_id="E1")]))
    svc.process_evaluation(evaluation(employee="FUNC-002", status="NON_COMPLIANT", evaluation_id="E1",
                                      violations=[viol(employee="FUNC-002", evaluation_id="E1")]))
    assert len(svc.list()) == 2


def test_not_evaluated_no_incident():
    svc, _c, _b = make_service()
    svc.process_evaluation(evaluation(employee=None, status="NOT_EVALUATED", evaluation_id="E1"))
    assert svc.list() == []

"""Histerese: COMPLIANT instantâneo NÃO fecha o incidente enquanto o Rules Engine
ainda lista a violação como confirmada (recuperação ainda não durou o mínimo)."""
from tests.conftest import evaluation, make_service, viol


def test_compliant_with_still_confirmed_violation_keeps_incident_open():
    svc, _, _ = make_service()
    svc.process_evaluation(evaluation(status="NON_COMPLIANT", violations=[viol()]))
    assert len(svc.list(status="OPEN")) == 1

    # Frame instantâneo OK, mas a violação segue na lista (histerese do Rules).
    out = svc.process_evaluation(evaluation(status="COMPLIANT", violations=[viol()]))
    assert out == []
    assert len(svc.list(status="OPEN")) == 1


def test_compliant_with_empty_violations_resolves_as_before():
    svc, _, _ = make_service()
    svc.process_evaluation(evaluation(status="NON_COMPLIANT", violations=[viol()]))
    svc.process_evaluation(evaluation(status="COMPLIANT", violations=[]))
    assert svc.list(status="OPEN") == []
    assert len(svc.list(status="RESOLVED")) == 1


def test_compliant_resolves_only_the_ppe_no_longer_violated():
    svc, _, _ = make_service()
    svc.process_evaluation(evaluation(status="NON_COMPLIANT",
                                      violations=[viol(ppe="helmet"), viol(ppe="vest")]))
    svc.process_evaluation(evaluation(status="COMPLIANT", violations=[viol(ppe="vest")]))
    open_ppes = {i.ppe_type for i in svc.list(status="OPEN")}
    assert open_ppes == {"vest"}

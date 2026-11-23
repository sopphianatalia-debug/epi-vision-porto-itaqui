import pytest

from app.domain.enums import EventType, IncidentStatus
from app.service import IncidentNotFound, InvalidReview
from tests.conftest import make_service, viol


def _open():
    svc, clock, bus = make_service()
    inc, _ = svc.record_violation(viol(evaluation_id="E1"))
    return svc, clock, bus, inc


def test_new_incident_starts_pending_review():
    _svc, _c, _b, inc = _open()
    assert inc.review_status == "PENDING"
    assert inc.reviewed_by is None and inc.review_history == []


def test_review_records_decision_note_and_reviewer():
    svc, clock, _b, inc = _open()
    clock.advance(5)
    r = svc.review_incident(inc.incident_id, "confirmed", "Sem capacete no vídeo.", "op.maria")
    assert r.review_status == "CONFIRMED"
    assert r.reviewed_by == "op.maria" and r.review_note == "Sem capacete no vídeo."
    assert r.reviewed_at is not None


def test_review_does_not_change_lifecycle_status():
    svc, _c, _b, inc = _open()
    svc.review_incident(inc.incident_id, "DISMISSED", "Falso positivo.", "op.maria")
    assert svc.get(inc.incident_id).status == IncidentStatus.OPEN


def test_review_requires_note_and_reviewer():
    svc, _c, _b, inc = _open()
    with pytest.raises(InvalidReview):
        svc.review_incident(inc.incident_id, "CONFIRMED", "  ", "op")
    with pytest.raises(InvalidReview):
        svc.review_incident(inc.incident_id, "CONFIRMED", "ok mesmo", " ")
    assert svc.get(inc.incident_id).review_status == "PENDING"


def test_review_rejects_unknown_decision_and_unknown_incident():
    svc, _c, _b, inc = _open()
    with pytest.raises(InvalidReview):
        svc.review_incident(inc.incident_id, "TALVEZ", "nota", "op")
    with pytest.raises(IncidentNotFound):
        svc.review_incident("INC-999999", "CONFIRMED", "nota", "op")


def test_review_history_is_append_only_audit_trail():
    svc, _c, _b, inc = _open()
    svc.review_incident(inc.incident_id, "INSUFFICIENT_EVIDENCE", "Imagem escura.", "op.a")
    svc.review_incident(inc.incident_id, "CONFIRMED", "Revi com outra câmera.", "sup.b")
    h = svc.get(inc.incident_id).review_history
    assert [x["decision"] for x in h] == ["INSUFFICIENT_EVIDENCE", "CONFIRMED"]
    assert [x["reviewer"] for x in h] == ["op.a", "sup.b"]
    assert svc.get(inc.incident_id).review_status == "CONFIRMED"


def test_review_publishes_event():
    svc, _c, bus, inc = _open()
    svc.review_incident(inc.incident_id, "CONFIRMED", "ok pelo vídeo", "op")
    assert bus.count(EventType.INCIDENT_REVIEWED) == 1

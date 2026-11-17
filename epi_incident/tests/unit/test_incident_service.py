from app.domain.enums import Action, EventType, IncidentStatus, Severity
from app.service import IncidentAlreadyResolved, IncidentNotFound, InvalidViolation
from tests.conftest import make_service, viol
import pytest


def test_create_incident():
    svc, _c, _b = make_service()
    inc, action = svc.record_violation(viol(evaluation_id="E1"))
    assert action == Action.CREATED
    assert inc.status == IncidentStatus.OPEN
    assert inc.incident_id == "INC-000001"


def test_incident_carries_employee_and_evaluation():
    svc, _c, _b = make_service()
    inc, _ = svc.record_violation(viol(employee="FUNC-777", evaluation_id="EVAL-9"))
    assert inc.employee_id == "FUNC-777"
    assert inc.evaluation_id == "EVAL-9" if False else inc.first_evaluation_id == "EVAL-9"


def test_severity_inherited_not_recalculated():
    svc, _c, _b = make_service()
    inc, _ = svc.record_violation(viol(ppe="gloves", severity="MEDIUM", evaluation_id="E1"))
    assert inc.severity == Severity.MEDIUM  # veio do Rules Engine, não recalculado


def test_reason_code_and_rule_preserved():
    svc, _c, _b = make_service()
    inc, _ = svc.record_violation(viol(reason_code="PPE_MISSING", version=7, evaluation_id="E1"))
    assert inc.reason_code == "PPE_MISSING"
    assert inc.rule_id == "RULE-1"
    assert inc.rule_version == 7


def test_deduplication_same_condition():
    svc, _c, _b = make_service()
    svc.record_violation(viol(evaluation_id="E1"))
    inc2, action = svc.record_violation(viol(evaluation_id="E2"))
    assert action == Action.UPDATED
    assert len([i for i in svc.list()]) == 1
    assert inc2.occurrence_count == 2


def test_occurrence_count_increments():
    svc, _c, _b = make_service()
    for i in range(5):
        svc.record_violation(viol(evaluation_id=f"E{i}"))
    assert svc.list()[0].occurrence_count == 5


def test_resolution_sets_fields_and_duration():
    svc, clock, _b = make_service()
    svc.record_violation(viol(evaluation_id="E1"))
    clock.advance(30.0)
    inc = svc.resolve_by_violation("FUNC-001", "RULE-1", "helmet")
    assert inc.status == IncidentStatus.RESOLVED
    assert inc.resolved_at is not None
    assert inc.duration_seconds(clock.now()) == 30.0


def test_open_duration_grows_with_clock():
    svc, clock, _b = make_service()
    inc, _ = svc.record_violation(viol(evaluation_id="E1"))
    clock.advance(10.0)
    assert inc.duration_seconds(clock.now()) == 10.0


def test_reopen_after_resolution_creates_new_incident():
    svc, clock, _b = make_service()
    svc.record_violation(viol(evaluation_id="E1"))
    clock.advance(5.0)
    svc.resolve_by_violation("FUNC-001", "RULE-1", "helmet")
    clock.advance(20.0)
    inc2, action = svc.record_violation(viol(evaluation_id="E2"))
    assert action == Action.CREATED
    assert inc2.incident_id == "INC-000002"
    ids = {i.incident_id: i.status for i in svc.list()}
    assert ids["INC-000001"] == IncidentStatus.RESOLVED
    assert ids["INC-000002"] == IncidentStatus.OPEN


def test_multiple_ppe_separate_incidents():
    svc, _c, _b = make_service()
    svc.record_violation(viol(ppe="helmet", evaluation_id="E1"))
    svc.record_violation(viol(ppe="gloves", evaluation_id="E1"))
    assert sorted(i.ppe_type for i in svc.list()) == ["gloves", "helmet"]


def test_multiple_cameras_no_duplication():
    svc, _c, _b = make_service()
    svc.record_violation(viol(evaluation_id="E1", cameras=["CAM-01"]))
    svc.record_violation(viol(evaluation_id="E2", cameras=["CAM-02"]))
    incidents = svc.list()
    assert len(incidents) == 1
    assert set(incidents[0].source_cameras) == {"CAM-01", "CAM-02"}


def test_different_employees_different_incidents():
    svc, _c, _b = make_service()
    svc.record_violation(viol(employee="FUNC-001", evaluation_id="E1"))
    svc.record_violation(viol(employee="FUNC-002", evaluation_id="E1"))
    assert len(svc.list()) == 2


def test_event_created_and_resolved_emitted_once():
    svc, clock, bus = make_service()
    svc.record_violation(viol(evaluation_id="E1"))
    svc.record_violation(viol(evaluation_id="E2"))  # UPDATED, não CREATED
    assert bus.count(EventType.INCIDENT_CREATED) == 1
    assert bus.count(EventType.INCIDENT_UPDATED) == 1
    svc.resolve_by_violation("FUNC-001", "RULE-1", "helmet")
    assert bus.count(EventType.INCIDENT_RESOLVED) == 1


def test_history_preserved_after_resolution():
    svc, _c, _b = make_service()
    svc.record_violation(viol(evaluation_id="E1"))
    svc.resolve_by_violation("FUNC-001", "RULE-1", "helmet")
    assert svc.get("INC-000001").status == IncidentStatus.RESOLVED  # continua consultável


def test_query_filters():
    svc, _c, _b = make_service()
    svc.record_violation(viol(employee="FUNC-001", ppe="helmet", severity="CRITICAL", evaluation_id="E1"))
    svc.record_violation(viol(employee="FUNC-002", ppe="gloves", severity="MEDIUM", evaluation_id="E1"))
    assert len(svc.list(employee_id="FUNC-001")) == 1
    assert len(svc.list(status="OPEN")) == 2
    assert len(svc.list(severity="CRITICAL")) == 1
    assert len(svc.list(ppe_type="gloves")) == 1


def test_ids_are_unique_and_sequential():
    svc, _c, _b = make_service()
    ids = []
    for i in range(3):
        inc, _ = svc.record_violation(viol(employee=f"FUNC-{i}", evaluation_id="E1"))
        ids.append(inc.incident_id)
    assert ids == ["INC-000001", "INC-000002", "INC-000003"]
    assert len(set(ids)) == 3


def test_missing_employee_raises():
    svc, _c, _b = make_service()
    with pytest.raises(InvalidViolation):
        svc.record_violation(viol(employee="", evaluation_id="E1"))


def test_missing_ppe_raises():
    svc, _c, _b = make_service()
    with pytest.raises(InvalidViolation):
        svc.record_violation(viol(ppe="", evaluation_id="E1"))


def test_resolve_unknown_incident_raises():
    svc, _c, _b = make_service()
    with pytest.raises(IncidentNotFound):
        svc.resolve_incident("INC-999999")


def test_resolve_already_resolved_raises():
    svc, _c, _b = make_service()
    inc, _ = svc.record_violation(viol(evaluation_id="E1"))
    svc.resolve_incident(inc.incident_id)
    with pytest.raises(IncidentAlreadyResolved):
        svc.resolve_incident(inc.incident_id)

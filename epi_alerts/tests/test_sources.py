from app.domain import AlertType, Severity
from app.sources import FusionSource, IncidentSource, TrackerSource
from tests.conftest import FakeHttp

T = "http://t"


def trackers_http(trackers, locations=None):
    data = {f"{T}/trackers": trackers}
    for tid, state in (locations or {}).items():
        data[f"{T}/trackers/{tid}/location"] = {"state": state}
    return FakeHttp(data)


def test_tracker_offline_low_battery_and_expired():
    http = trackers_http(
        [{"tracker_id": "T1", "status": "OFFLINE"}, {"tracker_id": "T2", "status": "LOW_BATTERY"},
         {"tracker_id": "T3", "status": "ACTIVE"}, {"tracker_id": "T4", "status": "ACTIVE"}],
        {"T3": "EXPIRED", "T4": "CURRENT"},
    )
    conds = {c.key: c for c in TrackerSource(http, T).collect()}
    assert set(conds) == {"tracker_offline:T1", "tracker_low_battery:T2", "tracker_location_expired:T3"}
    assert conds["tracker_location_expired:T3"].severity == Severity.INFO
    assert conds["tracker_offline:T1"].type == AlertType.TRACKER_OFFLINE


def test_healthy_trackers_generate_nothing():
    http = trackers_http([{"tracker_id": "T1", "status": "ACTIVE"}], {"T1": "CURRENT"})
    assert TrackerSource(http, T).collect() == []


def test_fusion_inconsistency_is_warning_and_never_accuses():
    http = FakeHttp({"http://f/fusion/ppe-inconsistencies": [{
        "employee_id": "FUNC-000234", "ppe_id": "PPE-1", "ppe_type": "helmet", "tracker_id": "T1",
        "camera_id": "CAM-1", "camera_area_id": "PATIO-02", "tracker_area_id": "ARMAZEM"}]})
    (c,) = FusionSource(http, "http://f").collect()
    assert c.severity == Severity.WARNING and c.type == AlertType.PPE_LOCATION_INCONSISTENCY
    assert "capacete" in c.message and "não indica, por si só, violação" in c.message


def test_incident_severity_mapping():
    def inc(i, sev):
        return {"incident_id": i, "employee_id": "FUNC-1", "ppe_type": "gloves", "severity": sev,
                "reason": "Luvas ausentes", "source_cameras": ["CAM-1"]}
    http = FakeHttp({"http://i/incidents?status=OPEN": [inc("1", "CRITICAL"), inc("2", "HIGH"),
                                                         inc("3", "MEDIUM"), inc("4", "LOW")]})
    sev = {c.key: c.severity for c in IncidentSource(http, "http://i").collect()}
    assert sev == {"incident:1": Severity.CRITICAL, "incident:2": Severity.CRITICAL,
                   "incident:3": Severity.WARNING, "incident:4": Severity.INFO}

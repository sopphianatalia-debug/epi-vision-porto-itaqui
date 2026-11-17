from app.api.deps import get_fusion_service, get_ppe_location_service

PREFIX = "/api/v1"


def _reset():
    get_fusion_service().reset_state()
    get_ppe_location_service().reset()


def test_ingest_and_read_employee_ppe_locations(client):
    _reset()
    payload = {"source": "tracker", "tracker_id": "TRACKER-001", "ppe_id": "HELMET-001",
               "ppe_type": "helmet", "employee_id_assigned": "FUNC-000234",
               "area_id": "PATIO-02", "location_state": "CURRENT", "confidence": 0.94}
    r = client.post(f"{PREFIX}/fusion/ppe-locations", json=payload)
    assert r.status_code == 200 and r.json()["proves_usage"] is False
    view = client.get(f"{PREFIX}/fusion/employees/FUNC-000234/ppe-locations").json()
    assert view["ppe_locations"][0]["ppe_id"] == "HELMET-001"
    assert view["inconsistencies"] == []


def test_invalid_confidence_returns_422(client):
    r = client.post(f"{PREFIX}/fusion/ppe-locations",
                    json={"tracker_id": "TRACKER-001", "confidence": 3})
    assert r.status_code == 422


def test_camera_area_and_inconsistency_end_to_end(client):
    _reset()
    client.post(f"{PREFIX}/fusion/cameras/CAM-ENTRY-02/area", json={"area_id": "PATIO-02"})
    client.post(f"{PREFIX}/fusion/observations", json={
        "camera_id": "CAM-ENTRY-02", "person_track_id": "T1", "identity_status": "MATCHED",
        "identity_confidence": 0.97, "employee_id": "FUNC-000234",
        "ppe": {"helmet": {"status": "DETECTED", "confidence": 0.96}},
    })
    client.post(f"{PREFIX}/fusion/ppe-locations", json={
        "tracker_id": "TRACKER-001", "ppe_id": "HELMET-001", "ppe_type": "helmet",
        "employee_id_assigned": "FUNC-000234", "area_id": "ARMAZEM", "location_state": "CURRENT"})
    items = client.get(f"{PREFIX}/fusion/ppe-inconsistencies").json()
    assert len(items) == 1 and items[0]["is_violation"] is False
    state = client.get(f"{PREFIX}/fusion/employees/FUNC-000234").json()
    assert state["ppe"]["helmet"]["status"] == "DETECTED"

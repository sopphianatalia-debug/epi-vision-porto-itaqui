"""
Testes de API (HTTP, via TestClient) — confirmam que os endpoints REST
expõem corretamente a lógica já validada em test_service.py. Não duplicam
os 24 cenários da seção 36 (isso já está coberto no nível de serviço) —
focam em contrato HTTP: status codes, formato de payload, erros 404/409.
"""
from __future__ import annotations

PREFIX = "/api/v1"


def test_health(client):
    resp = client.get(f"{PREFIX}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_root_health_without_prefix(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_register_and_get_tracker(client):
    resp = client.post(f"{PREFIX}/trackers", json={"technology": "MOCK", "tracker_id": "TRACKER-001"})
    assert resp.status_code == 201
    assert resp.json()["tracker_id"] == "TRACKER-001"

    resp2 = client.get(f"{PREFIX}/trackers/TRACKER-001")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "ACTIVE"


def test_register_duplicate_tracker_returns_409(client):
    client.post(f"{PREFIX}/trackers", json={"technology": "MOCK", "tracker_id": "TRACKER-001"})
    resp = client.post(f"{PREFIX}/trackers", json={"technology": "MOCK", "tracker_id": "TRACKER-001"})
    assert resp.status_code == 409


def test_get_unknown_tracker_returns_404(client):
    resp = client.get(f"{PREFIX}/trackers/TRACKER-INEXISTENTE")
    assert resp.status_code == 404


def test_register_ppe_and_assign(client):
    resp = client.post(f"{PREFIX}/ppe", json={"ppe_type": "helmet"})
    assert resp.status_code == 201
    ppe_id = resp.json()["ppe_id"]

    resp2 = client.post(f"{PREFIX}/ppe/{ppe_id}/assign", json={"employee_id": "FUNC-000234"})
    assert resp2.status_code == 200
    assert resp2.json()["employee_id"] == "FUNC-000234"
    assert resp2.json()["status"] == "ASSIGNED"


def test_register_area_and_checkpoint(client):
    resp = client.post(f"{PREFIX}/areas", json={"area_id": "PATIO-02", "name": "Pátio 02"})
    assert resp.status_code == 201

    resp2 = client.post(f"{PREFIX}/checkpoints", json={
        "area_id": "PATIO-02", "name": "Entrada Pátio 02",
        "checkpoint_id": "CHECKPOINT-PATIO-02", "camera_id": "CAM-ENTRY-02",
    })
    assert resp2.status_code == 201
    assert resp2.json()["camera_id"] == "CAM-ENTRY-02"


def test_checkpoint_unknown_area_returns_404(client):
    resp = client.post(f"{PREFIX}/checkpoints", json={"area_id": "AREA-X", "name": "X"})
    assert resp.status_code == 404


def test_demo_location_and_poll(client):
    client.post(f"{PREFIX}/trackers", json={"technology": "MOCK", "tracker_id": "TRACKER-001"})
    client.post(f"{PREFIX}/areas", json={"area_id": "PATIO-01", "name": "Pátio 01"})

    resp = client.post(f"{PREFIX}/demo/location", json={"tracker_id": "TRACKER-001", "area_id": "PATIO-01"})
    assert resp.status_code == 200

    resp2 = client.post(f"{PREFIX}/trackers/TRACKER-001/poll")
    assert resp2.status_code == 200
    assert resp2.json()["area_id"] == "PATIO-01"
    assert resp2.json()["status"] == "DETECTED"


def test_tracker_location_endpoint(client):
    client.post(f"{PREFIX}/trackers", json={"technology": "MOCK", "tracker_id": "TRACKER-001"})
    client.post(f"{PREFIX}/areas", json={"area_id": "PATIO-01", "name": "Pátio 01"})
    client.post(f"{PREFIX}/demo/location", json={"tracker_id": "TRACKER-001", "area_id": "PATIO-01"})
    client.post(f"{PREFIX}/trackers/TRACKER-001/poll")

    resp = client.get(f"{PREFIX}/trackers/TRACKER-001/location")
    assert resp.status_code == 200
    assert resp.json()["state"] == "CURRENT"
    assert resp.json()["area_id"] == "PATIO-01"


def test_safety_check_endpoint(client):
    client.post(f"{PREFIX}/areas", json={"area_id": "PATIO-02", "name": "Pátio 02"})
    client.post(f"{PREFIX}/checkpoints", json={
        "area_id": "PATIO-02", "name": "Entrada", "checkpoint_id": "CK-2",
    })

    resp = client.post(f"{PREFIX}/checks", json={
        "employee_id": "FUNC-000234", "area_id": "PATIO-02", "checkpoint_id": "CK-2",
        "status": "COMPLIANT", "detected_ppe": ["helmet", "vest", "boots"],
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "COMPLIANT"

    resp2 = client.get(f"{PREFIX}/employees/FUNC-000234/history")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 1


def test_fusion_observation_endpoint(client):
    client.post(f"{PREFIX}/trackers", json={"technology": "MOCK", "tracker_id": "TRACKER-001"})
    client.post(f"{PREFIX}/areas", json={"area_id": "PATIO-02", "name": "Pátio 02"})
    ppe_resp = client.post(f"{PREFIX}/ppe", json={"ppe_type": "helmet", "tracker_id": "TRACKER-001"})
    ppe_id = ppe_resp.json()["ppe_id"]
    client.post(f"{PREFIX}/ppe/{ppe_id}/assign", json={"employee_id": "FUNC-000234"})
    client.post(f"{PREFIX}/demo/location", json={"tracker_id": "TRACKER-001", "area_id": "PATIO-02"})
    client.post(f"{PREFIX}/trackers/TRACKER-001/poll")

    resp = client.get(f"{PREFIX}/trackers/TRACKER-001/fusion-observation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "tracker"
    assert body["employee_id_assigned"] == "FUNC-000234"
    assert body["area_id"] == "PATIO-02"


def test_inconsistency_check_endpoint(client):
    client.post(f"{PREFIX}/trackers", json={"technology": "MOCK", "tracker_id": "TRACKER-001"})
    client.post(f"{PREFIX}/areas", json={"area_id": "PATIO-02", "name": "Pátio 02"})
    client.post(f"{PREFIX}/areas", json={"area_id": "ARMAZEM", "name": "Armazém"})
    ppe_resp = client.post(f"{PREFIX}/ppe", json={"ppe_type": "helmet", "tracker_id": "TRACKER-001"})
    ppe_id = ppe_resp.json()["ppe_id"]
    client.post(f"{PREFIX}/ppe/{ppe_id}/assign", json={"employee_id": "FUNC-000234"})
    client.post(f"{PREFIX}/demo/location", json={"tracker_id": "TRACKER-001", "area_id": "ARMAZEM"})
    client.post(f"{PREFIX}/trackers/TRACKER-001/poll")

    resp = client.post(f"{PREFIX}/inconsistency-check", json={
        "employee_id": "FUNC-000234", "expected_area_id": "PATIO-02", "ppe_id": ppe_id,
    })
    assert resp.status_code == 200
    assert resp.json()["type"] == "POSSIBLE_INCONSISTENCY"
    assert resp.json()["ppe_area_id"] == "ARMAZEM"


def test_metrics_endpoint(client):
    client.post(f"{PREFIX}/trackers", json={"technology": "MOCK", "tracker_id": "TRACKER-001"})
    resp = client.get(f"{PREFIX}/metrics")
    assert resp.status_code == 200
    assert resp.json()["trackers_total"] == 1


def test_invalid_ppe_type_returns_422(client):
    resp = client.post(f"{PREFIX}/ppe", json={"ppe_type": "capacete-inexistente"})
    assert resp.status_code == 422


# --------------------------------------------------------------------- #
# Fase 3.8B — endpoints da interface: /employees, /inconsistencies, /events
# --------------------------------------------------------------------- #
def _seed_assigned_helmet(client, employee_id="FUNC-000234"):
    client.post(f"{PREFIX}/trackers", json={"technology": "MOCK", "tracker_id": "TRACKER-001"})
    client.post(f"{PREFIX}/areas", json={"area_id": "PATIO-02", "name": "Pátio 02"})
    client.post(f"{PREFIX}/areas", json={"area_id": "ARMAZEM", "name": "Armazém"})
    ppe_id = client.post(f"{PREFIX}/ppe", json={"ppe_type": "helmet", "tracker_id": "TRACKER-001"}).json()["ppe_id"]
    client.post(f"{PREFIX}/ppe/{ppe_id}/assign", json={"employee_id": employee_id})
    return ppe_id


def test_list_employees_empty(client):
    resp = client.get(f"{PREFIX}/employees")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_employees_derived_from_assigned_ppe(client):
    _seed_assigned_helmet(client)
    resp = client.get(f"{PREFIX}/employees")
    assert resp.status_code == 200
    ids = [e["employee_id"] for e in resp.json()]
    assert ids == ["FUNC-000234"]
    # ASSIGNED != WORN: o resumo lista EPIs atribuídos, sem afirmar uso.
    assert len(resp.json()[0]["assigned_ppe"]) == 1


def test_employee_summary_endpoint(client):
    _seed_assigned_helmet(client)
    resp = client.get(f"{PREFIX}/employees/FUNC-000234/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["employee_id"] == "FUNC-000234"
    assert body["assigned_ppe"][0]["ppe_type"] == "helmet"
    assert body["last_check"] is None
    assert body["history"] == []


def test_employee_summary_unknown_employee_is_empty_not_error(client):
    resp = client.get(f"{PREFIX}/employees/FUNC-NAO-EXISTE/summary")
    assert resp.status_code == 200
    assert resp.json()["assigned_ppe"] == []


def test_inconsistencies_endpoint_empty_then_populated(client):
    assert client.get(f"{PREFIX}/inconsistencies").json() == []

    ppe_id = _seed_assigned_helmet(client)
    client.post(f"{PREFIX}/demo/location", json={"tracker_id": "TRACKER-001", "area_id": "ARMAZEM"})
    client.post(f"{PREFIX}/trackers/TRACKER-001/poll")
    client.post(f"{PREFIX}/inconsistency-check", json={
        "employee_id": "FUNC-000234", "expected_area_id": "PATIO-02", "ppe_id": ppe_id,
    })

    items = client.get(f"{PREFIX}/inconsistencies").json()
    assert len(items) == 1
    # Inconsistência != violação: o tipo é sempre POSSIBLE_INCONSISTENCY.
    assert items[0]["type"] == "POSSIBLE_INCONSISTENCY"


def test_events_endpoint_returns_history_and_respects_limit(client):
    client.post(f"{PREFIX}/trackers", json={"technology": "MOCK", "tracker_id": "TRACKER-001"})
    client.post(f"{PREFIX}/areas", json={"area_id": "PATIO-01", "name": "Pátio 01"})
    client.post(f"{PREFIX}/areas", json={"area_id": "PATIO-02", "name": "Pátio 02"})
    for area in ("PATIO-01", "PATIO-02"):
        client.post(f"{PREFIX}/demo/location", json={"tracker_id": "TRACKER-001", "area_id": area})
        client.post(f"{PREFIX}/trackers/TRACKER-001/poll")

    resp = client.get(f"{PREFIX}/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 2
    assert all("event" in e and "payload" in e for e in events)
    assert any(e["event"] == "TRACKER_LOCATION_UPDATED" for e in events)

    limited = client.get(f"{PREFIX}/events", params={"limit": 1}).json()
    assert len(limited) == 1
    assert limited[0] == events[-1]


def test_camera_geo_validation_over_http(client):
    base = {"camera_id": "CAM-GEO", "name": "Geo", "sector": "PIER_BORDO", "kind": "INTERNA"}
    r = client.post("/api/v1/cameras", json={**base, "latitude": -2.57, "longitude": -44.36})
    assert r.status_code == 201 and r.json()["latitude"] == -2.57 and r.json()["longitude"] == -44.36
    assert client.post("/api/v1/cameras", json={**base, "camera_id": "G2", "latitude": -2.5}).status_code == 422   # só uma
    assert client.post("/api/v1/cameras", json={**base, "camera_id": "G3", "latitude": 91, "longitude": 0}).status_code == 422
    assert client.post("/api/v1/cameras", json={**base, "camera_id": "G4", "latitude": 0, "longitude": 181}).status_code == 422
    r = client.post("/api/v1/cameras", json={**base, "camera_id": "G5"})
    assert r.status_code == 201 and r.json()["latitude"] is None
    r = client.put("/api/v1/cameras/G5", json={**base, "camera_id": "G5", "latitude": -2.6, "longitude": -44.3})
    assert r.status_code == 200 and r.json()["longitude"] == -44.3

from tests.conftest import PREFIX
from tests.integration.test_api import _body


def test_ws_sends_snapshot_then_live_events(client):
    client.post(f"{PREFIX}/incidents", json=_body(employee_id="FUNC-WS0", evaluation_id="W0"))
    with client.websocket_connect(f"{PREFIX}/ws/incidents") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "SNAPSHOT"
        assert any(i["employee_id"] == "FUNC-WS0" for i in snap["incidents"])

        created = client.post(f"{PREFIX}/incidents", json=_body(employee_id="FUNC-WS1", evaluation_id="W1")).json()
        ev = ws.receive_json()
        assert ev["type"] == "INCIDENT_CREATED" and ev["incident_id"] == created["incident_id"]
        assert ev["review_status"] == "PENDING"

        client.post(f"{PREFIX}/incidents/{created['incident_id']}/review",
                    json={"decision": "CONFIRMED", "note": "visto no vídeo", "reviewer": "op"})
        ev = ws.receive_json()
        assert ev["type"] == "INCIDENT_REVIEWED" and ev["reviewer"] == "op"

        client.post(f"{PREFIX}/incidents/{created['incident_id']}/resolve")
        ev = ws.receive_json()
        assert ev["type"] == "INCIDENT_RESOLVED"


def test_ws_disconnect_unsubscribes(client):
    from app.api.deps import get_hub
    hub = get_hub()
    with client.websocket_connect(f"{PREFIX}/ws/incidents") as ws:
        ws.receive_json()
        assert hub.clients >= 1
    # após fechar, o cliente sai do hub (pode levar um instante)
    import time
    for _ in range(20):
        if hub.clients == 0:
            break
        time.sleep(0.05)
    assert hub.clients == 0

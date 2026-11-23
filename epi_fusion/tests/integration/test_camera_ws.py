"""Estado de sinal das câmeras (REST + WebSocket). Descreve só se a câmera está enviando dados."""
import time

from app.api.ws import diff_status
from app.config import get_settings
from app.observability import FusionMetrics
from tests.conftest import PREFIX


def _obs(camera, track="T1", employee="FUNC-000601"):
    return {"camera_id": camera, "person_track_id": track, "employee_id": employee,
            "identity_status": "MATCHED", "identity_confidence": 0.97,
            "ppe": {"helmet": {"status": "DETECTED", "confidence": 0.95}}}


def test_camera_status_online_then_offline_by_age():
    m = FusionMetrics()
    m.record_observation("CAM-A", 1.0, True, "F1")
    now = time.monotonic()
    assert m.camera_status(30, now_mono=now)[0]["status"] == "ONLINE"
    assert m.camera_status(30, now_mono=now + 31)[0]["status"] == "OFFLINE"
    assert m.camera_status(30, now_mono=now + 31)[0]["last_observation_at"] is not None


def test_camera_without_observation_is_not_listed():
    assert FusionMetrics().camera_status(30) == []


def test_diff_status_only_reports_changes():
    rows = [{"camera_id": "A", "status": "ONLINE", "last_observation_at": "t"},
            {"camera_id": "B", "status": "OFFLINE", "last_observation_at": "t"}]
    assert diff_status({"A": "ONLINE", "B": "ONLINE"}, rows) == [
        {"type": "CAMERA_STATUS_CHANGED", "camera_id": "B", "status": "OFFLINE",
         "previous_status": "ONLINE", "last_observation_at": "t"}]
    assert len(diff_status({}, rows)) == 2          # câmeras novas também geram evento
    assert diff_status({"A": "ONLINE", "B": "OFFLINE"}, rows) == []


def test_status_endpoint(client):
    client.post(f"{PREFIX}/fusion/observations", json=_obs("CAM-S1"))
    cams = client.get(f"{PREFIX}/fusion/cameras/status").json()["cameras"]
    assert any(c["camera_id"] == "CAM-S1" and c["status"] == "ONLINE" for c in cams)


def test_ws_announces_online_to_offline_and_back(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "camera_stale_seconds", 0.4)
    monkeypatch.setattr(s, "ws_poll_seconds", 0.1)
    client.post(f"{PREFIX}/fusion/observations", json=_obs("CAM-WS1"))
    with client.websocket_connect(f"{PREFIX}/fusion/ws/cameras") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "SNAPSHOT"
        assert any(c["camera_id"] == "CAM-WS1" and c["status"] == "ONLINE" for c in snap["cameras"])
        ev = _next_for(ws, "CAM-WS1")                    # a câmera fica em silêncio -> OFFLINE
        assert ev["status"] == "OFFLINE" and ev["previous_status"] == "ONLINE"
        client.post(f"{PREFIX}/fusion/observations", json=_obs("CAM-WS1", "T2"))   # volta a enviar
        ev = _next_for(ws, "CAM-WS1")
        assert ev["status"] == "ONLINE" and ev["previous_status"] == "OFFLINE"


def _next_for(ws, camera_id):
    for _ in range(50):
        ev = ws.receive_json()
        if ev.get("camera_id") == camera_id:
            return ev
    raise AssertionError("evento esperado não chegou")

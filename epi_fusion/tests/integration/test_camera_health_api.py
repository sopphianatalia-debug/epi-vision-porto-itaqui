"""Testes de integração do endpoint GET /fusion/cameras/health."""
from tests.conftest import PREFIX


def _obs(camera, track, employee, ppe, conf=0.97):
    return {
        "camera_id": camera, "person_track_id": track, "employee_id": employee,
        "identity_status": "MATCHED", "identity_confidence": conf, "ppe": ppe,
    }


def test_camera_health_endpoint_ok(client):
    client.post(f"{PREFIX}/fusion/observations",
                json=_obs("CAM-H1", "T1", "FUNC-000501",
                          {"helmet": {"status": "DETECTED", "confidence": 0.95}}))
    r = client.get(f"{PREFIX}/fusion/cameras/health")
    assert r.status_code == 200
    cams = r.json()["cameras"]
    assert any(c["camera_id"] == "CAM-H1" for c in cams)


def test_camera_health_schema_fields(client):
    client.post(f"{PREFIX}/fusion/observations",
                json=_obs("CAM-H2", "T1", "FUNC-000502",
                          {"helmet": {"status": "DETECTED", "confidence": 0.9}}))
    row = next(c for c in client.get(f"{PREFIX}/fusion/cameras/health").json()["cameras"]
               if c["camera_id"] == "CAM-H2")
    for field in ("camera_id", "observations", "identity_matches", "identity_match_rate",
                  "anonymous", "conflicts", "avg_confidence", "not_visible",
                  "not_visible_rate", "health_score"):
        assert field in row
    assert isinstance(row["observations"], int)


def test_camera_health_not_visible_via_pipeline(client):
    # Câmera reporta NOT_VISIBLE -> deve refletir na saúde da câmera (sem virar MISSING).
    client.post(f"{PREFIX}/fusion/observations",
                json=_obs("CAM-NV", "T1", "FUNC-000503",
                          {"boots": {"status": "NOT_VISIBLE", "confidence": 0.0},
                           "helmet": {"status": "DETECTED", "confidence": 0.9}}))
    row = next(c for c in client.get(f"{PREFIX}/fusion/cameras/health").json()["cameras"]
               if c["camera_id"] == "CAM-NV")
    assert row["not_visible"] >= 1
    assert row["not_visible_rate"] is not None


def test_metrics_still_intact(client):
    client.post(f"{PREFIX}/fusion/observations",
                json=_obs("CAM-H3", "T1", "FUNC-000504",
                          {"helmet": {"status": "DETECTED", "confidence": 0.9}}))
    m = client.get(f"{PREFIX}/fusion/metrics").json()
    # Todos os campos globais continuam presentes.
    for field in ("observations_total", "observations_per_second", "fusion_latency_ms",
                  "active_employee_states", "anonymous_observations", "fusion_conflicts",
                  "expired_states", "identity_match_rate", "observations_by_camera"):
        assert field in m

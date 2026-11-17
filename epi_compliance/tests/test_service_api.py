from app.compliance import build_compliance_service
from app.enums import ComplianceStatus, PPEStatus
from tests.conftest import PREFIX, default_settings, full_body_obs, ppe


def full_ppe():
    return [
        ppe("helmet", 360, 110, 440, 180),
        ppe("vest", 325, 270, 475, 520),
        ppe("gloves", 310, 470, 360, 520),   # mão esquerda
        ppe("gloves", 440, 470, 490, 520),   # mão direita
        ppe("boots", 340, 830, 460, 895),
    ]


def test_service_full_ppe_becomes_compliant_over_time():
    svc = build_compliance_service(default_settings(temporal_min_frames=3, required_ppe=["helmet", "vest", "gloves", "boots"]))
    result = None
    for _ in range(4):
        result, _ev = svc.evaluate(full_body_obs(ppe_list=full_ppe()))
    assert result.overall == ComplianceStatus.COMPLIANT
    assert result.helmet.status == PPEStatus.PROPER


def test_service_missing_glove_generates_evidence():
    svc = build_compliance_service(default_settings(temporal_min_frames=2, required_ppe=["helmet", "vest", "gloves", "boots"]))
    only_left = [p for p in full_ppe() if not (p.ppe_type == "gloves" and p.bbox.x1 > 400)]
    result = None
    for _ in range(3):
        result, evidence = svc.evaluate(full_body_obs(ppe_list=only_left))
    assert result.overall == ComplianceStatus.PARTIAL_NON_COMPLIANCE
    assert svc.evidence.count >= 1
    kinds = {e["ppe_type"] for e in svc.evidence.recent()}
    assert "glove_right" in kinds


def test_service_boots_not_visible_is_undetermined_not_missing():
    from app.types import PersonObservation
    from tests.conftest import bbox
    svc = build_compliance_service(default_settings(temporal_min_frames=2, required_ppe=["helmet", "vest", "boots"]))
    # câmera de torso: helmet+vest ok, botas fora de quadro
    obs_ppe = [ppe("helmet", 360, 110, 440, 180), ppe("vest", 325, 270, 475, 520)]
    result = None
    for _ in range(3):
        obs = PersonObservation("T9", bbox(300, 100, 500, 600), 1000, 600, ppe=obs_ppe)
        result, _ev = svc.evaluate(obs)
    assert result.boots.status == PPEStatus.NOT_VISIBLE
    assert result.overall == ComplianceStatus.UNDETERMINED  # não é NON_COMPLIANT


# ---------- API ----------

def _frame_payload(ppe_items, track="TRACK-000123"):
    return {
        "person_track_id": track,
        "person_bbox": [300, 100, 500, 900],
        "frame_width": 1000, "frame_height": 1000,
        "employee_id": "FUNC-000002", "camera_id": "CAM-07",
        "ppe": [{"ppe_type": p.ppe_type, "bbox": p.bbox.as_list(), "confidence": p.confidence}
                for p in ppe_items],
    }


def test_api_evaluate(client):
    payload = _frame_payload(full_ppe(), track="TRACK-EVAL")
    # Análise temporal: alguns frames consistentes antes de concluir com confiança.
    body = None
    for _ in range(4):
        r = client.post(f"{PREFIX}/compliance/evaluate", json=payload)
        assert r.status_code == 200
        body = r.json()
    assert body["result"]["helmet"]["status"] == "PROPER"
    assert "overall" in body["result"]
    assert body["dashboard"]["overall"]["emoji"]


def test_api_batch_temporal(client):
    frames = [_frame_payload(full_ppe(), track="TRACK-BATCH") for _ in range(4)]
    r = client.post(f"{PREFIX}/compliance/evaluate-batch", json={"frames": frames})
    assert r.status_code == 200
    body = r.json()
    assert body["frames_processed"] == 4
    assert body["final"]["overall"] == "COMPLIANT"


def test_api_dashboard_html(client):
    r = client.get(f"{PREFIX}/dashboard")
    assert r.status_code == 200
    assert "Dashboard de Conformidade" in r.text


def test_api_evidence_and_state(client):
    # gera não conformidade (sem luvas nem botas)
    payload = _frame_payload([ppe("helmet", 360, 110, 440, 180), ppe("vest", 325, 270, 475, 520)], track="TRACK-EV")
    for _ in range(3):
        client.post(f"{PREFIX}/compliance/evaluate", json=payload)
    assert client.get(f"{PREFIX}/compliance/state").status_code == 200
    assert client.get(f"{PREFIX}/compliance/evidence").status_code == 200

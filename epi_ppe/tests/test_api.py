from tests.conftest import PREFIX, frame, person, ppe


def test_health(client):
    r = client.get(f"{PREFIX}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_classes_endpoint(client):
    r = client.get(f"{PREFIX}/classes")
    assert r.status_code == 200
    body = r.json()
    assert "PERSON" in body["classes"]
    assert "HELMET" in body["thresholds"]


def test_detect_endpoint(client):
    scene = frame(person(100, 100, 300, 500), ppe("HELMET", 150, 110, 230, 160))
    r = client.post(f"{PREFIX}/detect", json={"camera_id": "CAM-07", "frame": scene})
    assert r.status_code == 200
    types = {d["type"] for d in r.json()["detections"]}
    assert {"PERSON", "HELMET"} <= types


def test_process_frame_associates_ppe(client):
    scene = frame(
        person(100, 100, 300, 500),
        ppe("HELMET", 150, 110, 230, 160),
        ppe("SAFETY_VEST", 130, 230, 270, 380),
    )
    r = client.post(f"{PREFIX}/pipeline/process-frame", json={"camera_id": "CAM-07", "frame": scene})
    assert r.status_code == 200
    persons = r.json()["persons"]
    assert len(persons) == 1
    assert persons[0]["person_track_id"].startswith("TRACK-")
    ppe_types = {d["type"] for d in persons[0]["detections"]}
    assert {"HELMET", "SAFETY_VEST"} <= ppe_types


def test_events_and_metrics(client):
    scene = frame(person(100, 100, 300, 500), ppe("HELMET", 150, 110, 230, 160))
    client.post(f"{PREFIX}/pipeline/process-frame", json={"camera_id": "CAM-07", "frame": scene})
    assert client.get(f"{PREFIX}/events").status_code == 200
    metrics = client.get(f"{PREFIX}/metrics").json()
    assert metrics["frames_processed"] >= 1


def test_evaluate_endpoint(client):
    payload = {
        "predictions": {"img1": [{"cls": "HELMET", "bbox": [10, 10, 60, 60], "confidence": 0.95}]},
        "ground_truth": {"img1": [{"cls": "HELMET", "bbox": [11, 11, 61, 61]}]},
        "classes": ["HELMET"],
    }
    r = client.post(f"{PREFIX}/evaluate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["mAP"] == 1.0
    assert body["per_class"][0]["precision"] == 1.0

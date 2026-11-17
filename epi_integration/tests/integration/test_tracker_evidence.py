"""Tracker -> Fusion dentro do pipeline da câmera.

Usa clientes falsos (sem subir serviços): o que se verifica é a ORQUESTRAÇÃO —
quando a evidência de localização é lida e enviada, que falhas não derrubam o
frame e que o tracker nunca interfere na conformidade.
"""
from __future__ import annotations

from app.camera_pipeline import RealCameraPipeline


class FakeVision:
    def process_frame(self, camera_id, frame):
        return {"persons": [{
            "person_track_id": "TRK-1", "employee_id": None, "person_confidence": 0.9,
            "person_bbox": [0, 0, 10, 10],
            "detections": [{"type": "HELMET", "confidence": 0.96, "bbox": [0, 0, 5, 5]}],
        }]}


class FakeIdentity:
    def __init__(self, status="MATCHED"):
        self.status = status

    def match(self, camera_id, seed, person_track_id):
        return {"status": self.status, "employee_id": "FUNC-000234", "confidence": 0.97}


class FakeFusion:
    def __init__(self, fail_location=False):
        self.fail_location = fail_location
        self.locations, self.areas, self.ingested = [], [], 0

    def ingest(self, **kw):
        self.ingested += 1
        return {}

    def get_employee_state(self, employee_id):
        return {"employee_id": employee_id, "identity_status": "MATCHED", "ppe": {
            "helmet": {"status": "DETECTED", "confidence": 0.96, "cameras": ["CAM-ENTRY-02"]}}}

    def send_ppe_location(self, obs):
        if self.fail_location:
            raise RuntimeError("fusion indisponível")
        self.locations.append(obs)
        return obs

    def set_camera_area(self, camera_id, area_id):
        self.areas.append((camera_id, area_id))


class FakeRules:
    def evaluate(self, **kw):
        return {"overall_status": "COMPLIANT", "violations": [], "evaluation_id": "EV-1"}


class FakeIncident:
    def process_evaluation(self, evaluation):
        return []


class FakeTracker:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def get_employee_summary(self, employee_id):
        self.calls += 1
        if self.fail:
            raise RuntimeError("tracker fora do ar")
        return {"assigned_ppe": [{"tracker_id": "TRACKER-001"}, {"tracker_id": None}]}

    def get_fusion_observation(self, tracker_id):
        return {"source": "tracker", "tracker_id": tracker_id, "ppe_id": "HELMET-001",
                "ppe_type": "helmet", "employee_id_assigned": "FUNC-000234",
                "area_id": "PATIO-02", "location_state": "CURRENT"}


def build(tracker=None, fusion=None, identity=None, **kw):
    fusion = fusion or FakeFusion()
    pipe = RealCameraPipeline(
        FakeVision(), identity or FakeIdentity(), fusion, FakeRules(), FakeIncident(),
        process_every_n_frames=1, tracker_client=tracker, **kw,
    )
    return pipe, fusion


def test_without_tracker_nothing_is_sent_and_status_disabled():
    pipe, fusion = build(tracker=None)
    results = pipe.process_frame("CAM-ENTRY-02", {})
    assert results[0].overall_status == "COMPLIANT"
    assert fusion.locations == []
    assert pipe.status.snapshot()["tracker"] == "DISABLED"


def test_tracker_evidence_is_forwarded_to_fusion_and_area_registered_once():
    tracker = FakeTracker()
    pipe, fusion = build(tracker=tracker, tracker_area_id="PATIO-02", tracker_sync_interval_seconds=0)
    pipe.process_frame("CAM-ENTRY-02", {})
    pipe.process_frame("CAM-ENTRY-02", {})
    assert [l["tracker_id"] for l in fusion.locations] == ["TRACKER-001", "TRACKER-001"]
    assert fusion.areas == [("CAM-ENTRY-02", "PATIO-02")]
    assert pipe.status.snapshot()["tracker"] == "ONLINE"
    assert pipe.metrics.snapshot()["tracker_evidence_sent"] == 2


def test_sync_is_throttled_per_employee():
    tracker = FakeTracker()
    now = [100.0]
    pipe, fusion = build(tracker=tracker, tracker_sync_interval_seconds=5.0)
    pipe._clock = lambda: now[0]
    pipe.process_frame("CAM-ENTRY-02", {})
    now[0] += 1
    pipe.process_frame("CAM-ENTRY-02", {})
    assert tracker.calls == 1
    now[0] += 5
    pipe.process_frame("CAM-ENTRY-02", {})
    assert tracker.calls == 2


def test_tracker_failure_never_breaks_the_frame_or_changes_compliance():
    pipe, fusion = build(tracker=FakeTracker(fail=True))
    results = pipe.process_frame("CAM-ENTRY-02", {})
    assert results[0].overall_status == "COMPLIANT"
    assert pipe.status.snapshot()["tracker"] == "ERROR"
    assert pipe.metrics.snapshot()["errors_by_service"]["tracker"] == 1


def test_fusion_rejecting_location_does_not_break_the_frame():
    pipe, fusion = build(tracker=FakeTracker(), fusion=FakeFusion(fail_location=True))
    results = pipe.process_frame("CAM-ENTRY-02", {})
    assert results[0].overall_status == "COMPLIANT"
    assert pipe.status.snapshot()["tracker"] == "ERROR"


def test_unidentified_person_never_triggers_tracker_lookup():
    tracker = FakeTracker()
    pipe, fusion = build(tracker=tracker, identity=FakeIdentity(status="UNKNOWN"))
    pipe.process_frame("CAM-ENTRY-02", {})
    assert tracker.calls == 0 and fusion.locations == []

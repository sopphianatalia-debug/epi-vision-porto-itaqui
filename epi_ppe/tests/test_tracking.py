from app.enums import DetectionClass
from app.tracking import PersonTracker
from app.types import BoundingBox, Detection


def person(x1, y1, x2, y2):
    return Detection(DetectionClass.PERSON, 0.95, BoundingBox(x1, y1, x2, y2))


def test_track_id_format_and_persistence():
    tracker = PersonTracker(iou_threshold=0.3, track_ttl_frames=5)
    a = tracker.update([person(0, 0, 100, 200)])
    tid = a[0][0]
    assert tid == "TRACK-000001"

    # Frame seguinte, caixa levemente deslocada -> mesmo ID.
    b = tracker.update([person(5, 5, 105, 205)])
    assert b[0][0] == tid


def test_new_person_gets_new_id():
    tracker = PersonTracker()
    tracker.update([person(0, 0, 100, 200)])
    out = tracker.update([person(0, 0, 100, 200), person(500, 0, 600, 200)])
    ids = {tid for tid, _ in out}
    assert "TRACK-000002" in ids


def test_track_expires_after_ttl():
    tracker = PersonTracker(track_ttl_frames=3)
    tracker.update([person(0, 0, 100, 200)])
    for _ in range(4):
        tracker.update([])  # sem detecções
    assert tracker.active_tracks == []

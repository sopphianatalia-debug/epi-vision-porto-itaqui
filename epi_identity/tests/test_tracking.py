from datetime import datetime, timedelta, timezone

from app.enums import TrackState
from app.recognition.types import BoundingBox
from app.tracking import Detection, IdentityManager, IoUTracker
from app.tracking.tracker import iou


def _now():
    return datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)


def test_iou_basic():
    a = BoundingBox(0, 0, 10, 10)
    b = BoundingBox(0, 0, 10, 10)
    assert abs(iou(a, b) - 1.0) < 1e-9
    c = BoundingBox(100, 100, 110, 110)
    assert iou(a, c) == 0.0


def test_tracker_keeps_same_id_across_frames():
    tracker = IoUTracker("CAM07", iou_threshold=0.3, track_ttl_seconds=15)
    t0 = _now()
    tracks = tracker.update([Detection(BoundingBox(0, 0, 100, 100))], t0)
    code = tracks[0].track_code
    assert code.startswith("CAM07_PERSON_")

    # Frame seguinte, caixa levemente deslocada -> mesmo track.
    tracks = tracker.update([Detection(BoundingBox(5, 5, 105, 105))], t0 + timedelta(seconds=1))
    assert len(tracks) == 1
    assert tracks[0].track_code == code
    assert tracks[0].hits == 2


def test_tracker_creates_new_id_for_disjoint_box():
    tracker = IoUTracker("CAM07")
    t0 = _now()
    tracker.update([Detection(BoundingBox(0, 0, 50, 50))], t0)
    tracks = tracker.update([Detection(BoundingBox(500, 500, 550, 550))], t0)
    codes = {t.track_code for t in tracks}
    assert len(codes) == 2


def test_tracker_expires_track():
    tracker = IoUTracker("CAM07", track_ttl_seconds=10)
    t0 = _now()
    tracker.update([Detection(BoundingBox(0, 0, 50, 50))], t0)
    # Sem detecções por tempo > ttl -> track encerrado.
    tracker.update([], t0 + timedelta(seconds=20))
    assert all(t.state != TrackState.ACTIVE for t in tracker._tracks.values())  # noqa: SLF001


def test_identity_persists_during_ttl_then_expires():
    mgr = IdentityManager(identity_ttl_seconds=30, revalidate_after_seconds=10)
    t0 = _now()
    mgr.assign("CAM07_PERSON_00001", "FUNC-000234", confidence=0.96, now=t0)

    # Dentro do TTL: identidade mantida mesmo sem novo rosto (reidentificação).
    ident = mgr.get_identity("CAM07_PERSON_00001", now=t0 + timedelta(seconds=25))
    assert ident is not None and ident.employee_code == "FUNC-000234"

    # Após revalidate_after: pede revalidação.
    assert mgr.should_revalidate("CAM07_PERSON_00001", now=t0 + timedelta(seconds=15)) is True

    # Além do TTL: identidade expira.
    ident = mgr.get_identity("CAM07_PERSON_00001", now=t0 + timedelta(seconds=40))
    assert ident is None


def test_identity_touch_renews_validation():
    mgr = IdentityManager(identity_ttl_seconds=30)
    t0 = _now()
    mgr.assign("T1", "FUNC-1", 0.9, t0)
    mgr.touch("T1", now=t0 + timedelta(seconds=25), confidence=0.98)
    ident = mgr.get_identity("T1", now=t0 + timedelta(seconds=45))
    assert ident is not None
    assert ident.confidence == 0.98

"""Reconhecimento facial na câmera (opt-in): recorte, cache por status, nada de demo seed, nada de imagem em log."""
from __future__ import annotations

import base64
import logging

import numpy as np
import pytest

from app.camera_pipeline import RealCameraPipeline
from app.face_probe import face_probe_b64
from app.identity_cache import IdentityCache


# ------------------------------------------------------------------ recorte
def _frame(h=480, w=640):
    return np.random.default_rng(0).integers(0, 255, (h, w, 3), dtype=np.uint8)


def test_probe_is_jpeg_of_upper_part_only():
    b64 = face_probe_b64(_frame(), [100, 40, 300, 440])
    data = base64.b64decode(b64)
    assert data[:3] == b"\xff\xd8\xff"
    import cv2
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[1] == 200 and abs(img.shape[0] - 180) <= 1      # largura da pessoa, 45% da altura


@pytest.mark.parametrize("bbox", [None, [1, 2, 3], [0, 0, 40, 40], [700, 10, 800, 400]])
def test_probe_none_for_bad_or_tiny_boxes(bbox):
    assert face_probe_b64(_frame(), bbox) is None


def test_probe_none_without_frame():
    assert face_probe_b64(None, [0, 0, 100, 100]) is None


# ------------------------------------------------------------------ cache com TTL por entrada
def test_cache_ttl_override_per_entry():
    t = [0.0]
    from datetime import datetime, timedelta, timezone
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cache = IdentityCache(ttl_seconds=2.0, clock=lambda: base + timedelta(seconds=t[0]))
    f = {"employee_id": "E", "identity_status": "MATCHED", "identity_confidence": 0.9}
    cache.put("C", "T1", f, ttl_seconds=15)
    cache.put("C", "T2", f)
    t[0] = 10
    assert cache.get("C", "T1") is not None and cache.get("C", "T2") is None


# ------------------------------------------------------------------ pipeline
class _Vision:
    def process_frame_image(self, camera_id, frame):
        return {"persons": [{"person_track_id": "T", "employee_id": None, "person_confidence": 0.9,
                             "person_bbox": [100, 40, 300, 440], "detections": []}]}


class _Fus:
    def ingest(self, **kw):
        return {}

    def get_employee_state(self, e):
        return {"employee_id": e, "identity_status": "MATCHED", "ppe": {}}


class _Rul:
    def evaluate(self, **kw):
        return {"overall_status": "INDETERMINATE", "violations": [], "evaluation_id": "E"}


class _Inc:
    def process_evaluation(self, ev):
        return []


class _FaceId:
    def __init__(self, status="MATCHED", employee="FUNC-000007", fail=False):
        self.calls, self.seed_calls, self.images = 0, 0, []
        self.status, self.employee, self.fail = status, employee, fail

    def match(self, **kw):
        self.seed_calls += 1
        return {"status": "MATCHED", "employee_id": "FUNC-DEMO", "confidence": 1.0}

    def match_image(self, camera_id, image_base64, person_track_id=None):
        self.calls += 1
        self.images.append(image_base64)
        if self.fail:
            raise RuntimeError("identity fora do ar")
        return {"status": self.status, "employee_id": self.employee if self.status == "MATCHED" else None,
                "confidence": 0.7 if self.status == "MATCHED" else 0.0}


def _pipe(ident, face=True, clock=None, **kw):
    return RealCameraPipeline(_Vision(), ident, _Fus(), _Rul(), _Inc(), process_every_n_frames=1,
                              use_real_images=True, face_recognition=face,
                              identity_cache=IdentityCache(ttl_seconds=2.0, **({"clock": clock} if clock else {})),
                              identity_seed_provider=lambda c, t: "FUNC-DEMO", **kw)


def _id_of(res):
    return res[0].employee_id, res[0].identity_status


def test_face_mode_uses_face_not_demo_seed():
    ident = _FaceId()
    res = _pipe(ident).process_frame("CAM", _frame())
    assert _id_of(res) == ("FUNC-000007", "MATCHED")
    assert ident.calls == 1 and ident.seed_calls == 0


def test_face_off_by_default_keeps_demo_seed():
    ident = _FaceId()
    res = _pipe(ident, face=False).process_frame("CAM", _frame())
    assert _id_of(res)[0] == "FUNC-DEMO" and ident.calls == 0 and ident.seed_calls == 1


def test_matched_is_cached_longer_than_default():
    from datetime import datetime, timedelta, timezone
    t = [0.0]
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ident = _FaceId()
    pipe = _pipe(ident, clock=lambda: base + timedelta(seconds=t[0]), face_matched_ttl_seconds=15)
    pipe.process_frame("CAM", _frame())
    t[0] = 10
    pipe.process_frame("CAM", _frame())
    assert ident.calls == 1                      # ainda em cache aos 10 s
    t[0] = 20
    pipe.process_frame("CAM", _frame())
    assert ident.calls == 2


def test_unknown_is_retried_soon_and_never_becomes_an_employee():
    from datetime import datetime, timedelta, timezone
    t = [0.0]
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ident = _FaceId(status="UNKNOWN")
    pipe = _pipe(ident, clock=lambda: base + timedelta(seconds=t[0]), face_retry_seconds=2)
    res = pipe.process_frame("CAM", _frame())
    assert res[0].employee_id is None
    t[0] = 3
    pipe.process_frame("CAM", _frame())
    assert ident.calls == 2


def test_tiny_person_box_is_not_identified_and_does_not_call_identity():
    class _Tiny(_Vision):
        def process_frame_image(self, camera_id, frame):
            r = super().process_frame_image(camera_id, frame)
            r["persons"][0]["person_bbox"] = [100, 40, 140, 100]
            return r
    ident = _FaceId()
    pipe = RealCameraPipeline(_Tiny(), ident, _Fus(), _Rul(), _Inc(), process_every_n_frames=1,
                              use_real_images=True, face_recognition=True)
    res = pipe.process_frame("CAM", _frame())
    assert res[0].employee_id is None and ident.calls == 0


def test_identity_failure_does_not_break_the_frame():
    res = _pipe(_FaceId(fail=True)).process_frame("CAM", _frame())
    assert res[0].employee_id is None


def test_no_image_data_in_logs(caplog):
    ident = _FaceId()
    with caplog.at_level(logging.DEBUG):
        _pipe(ident).process_frame("CAM", _frame())
    assert ident.images and all(img[:40] not in caplog.text for img in ident.images)

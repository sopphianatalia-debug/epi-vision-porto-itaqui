"""Recorte de evidência: só a pessoa (com margem), caixas relativas ao recorte, envio best-effort."""
import numpy as np

from app.camera_pipeline import RealCameraPipeline
from app.evidence_crop import build_evidence


def _frame(w=640, h=480):
    return np.full((h, w, 3), 120, dtype=np.uint8)


def test_crop_is_person_only_with_margin_and_boxes_are_relative():
    jpeg, dets = build_evidence(_frame(), [100, 100, 200, 300],
                                [{"type": "HELMET", "confidence": 0.9, "bbox": [120, 100, 180, 140]}],
                                {"helmet": "MISSING"})
    import cv2
    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[1] < 200 and img.shape[0] < 300        # nada do quadro inteiro (640x480)
    assert img.shape[1] >= 100 and img.shape[0] >= 200       # corpo inteiro cabe (com margem)
    d = dets[0]
    assert d["label"] == "helmet" and d["status"] == "MISSING" and d["confidence"] == 0.9
    assert all(0 <= v <= 1 for v in d["bbox"]) and d["bbox"][0] + d["bbox"][2] <= 1.001


def test_crop_clamps_at_frame_edge_and_drops_boxes_outside():
    jpeg, dets = build_evidence(_frame(), [0, 0, 80, 120], [{"type": "vest", "bbox": [500, 400, 600, 450]}])
    assert jpeg and dets == []


def test_no_crop_without_real_image_or_valid_box():
    assert build_evidence({"fake": "scene"}, [0, 0, 10, 10], []) is None
    assert build_evidence(_frame(), [50, 50, 40, 40], []) is None
    assert build_evidence(_frame(), [10, 10, 12, 12], []) is None


def test_large_crop_is_scaled_down_to_limit():
    jpeg, _ = build_evidence(_frame(3000, 2000), [0, 0, 3000, 2000], [])
    import cv2
    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert max(img.shape[:2]) <= 1280


class _Inc:
    def __init__(self, ok=True, boom=False):
        self.calls, self.ok, self.boom = [], ok, boom

    def upload_evidence(self, iid, jpeg, dets):
        if self.boom:
            raise RuntimeError("rede")
        self.calls.append((iid, len(jpeg), dets))
        return self.ok


def _pipe(inc, send=True):
    p = object.__new__(RealCameraPipeline)
    p._send_evidence, p._incident = send, inc
    return p


PERSON = {"person_bbox": [100, 100, 200, 300], "detections": [{"type": "helmet", "bbox": [120, 100, 180, 140]}]}


def test_attach_sends_crop_only_when_enabled():
    inc = _Inc()
    _pipe(inc)._attach_evidence("INC-1", _frame(), PERSON, {"helmet": {"status": "MISSING"}})
    assert inc.calls and inc.calls[0][0] == "INC-1" and inc.calls[0][2][0]["status"] == "MISSING"
    off = _Inc()
    _pipe(off, send=False)._attach_evidence("INC-1", _frame(), PERSON, {})
    assert off.calls == []


def test_attach_never_raises_and_skips_non_images():
    _pipe(_Inc(boom=True))._attach_evidence("INC-1", _frame(), PERSON, {})
    _pipe(_Inc(ok=False))._attach_evidence("INC-1", _frame(), PERSON, {})
    skip = _Inc()
    _pipe(skip)._attach_evidence("INC-1", {"fake": 1}, PERSON, {})
    assert skip.calls == []

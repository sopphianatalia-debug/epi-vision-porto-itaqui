"""Recorte de evidência: só a pessoa (com margem), caixas relativas ao recorte, envio best-effort."""
import numpy as np

from app.camera_pipeline import RealCameraPipeline
from app.evidence_crop import build_evidence, build_findings


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
    assert dets[0]['label'] == 'person' and 0 <= dets[0]['bbox'][0] <= 1 and dets[0]['bbox'][2] <= 1.001
    d = dets[1]
    assert d["label"] == "helmet" and d["status"] == "MISSING" and d["confidence"] == 0.9
    assert all(0 <= v <= 1 for v in d["bbox"]) and d["bbox"][0] + d["bbox"][2] <= 1.001


def test_crop_clamps_at_frame_edge_and_drops_boxes_outside():
    jpeg, dets = build_evidence(_frame(), [0, 0, 80, 120], [{"type": "vest", "bbox": [500, 400, 600, 450]}])
    assert jpeg and [d['label'] for d in dets] == ['person']


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

    def upload_evidence(self, iid, jpeg, dets, findings=None):
        if self.boom:
            raise RuntimeError("rede")
        self.calls.append((iid, len(jpeg), dets))
        self.last_jpeg = jpeg
        return self.ok


def _pipe(inc, send=True):
    p = object.__new__(RealCameraPipeline)
    p._send_evidence, p._incident, p._evidence_pending, p._evidence_best = send, inc, {}, {}
    return p


PERSON = {"person_bbox": [100, 100, 200, 300], "detections": [{"type": "helmet", "bbox": [120, 100, 180, 140]}]}


def test_attach_sends_crop_only_when_enabled():
    inc = _Inc()
    _pipe(inc)._attach_evidence("INC-1", _frame(), PERSON, {"helmet": {"status": "MISSING"}})
    assert inc.calls and inc.calls[0][0] == "INC-1" and inc.calls[0][2][1]["status"] == "MISSING"
    off = _Inc()
    _pipe(off, send=False)._attach_evidence("INC-1", _frame(), PERSON, {})
    assert off.calls == []


def test_attach_never_raises_and_skips_non_images():
    _pipe(_Inc(boom=True))._attach_evidence("INC-1", _frame(), PERSON, {})
    _pipe(_Inc(ok=False))._attach_evidence("INC-1", _frame(), PERSON, {})
    skip = _Inc()
    _pipe(skip)._attach_evidence("INC-1", {"fake": 1}, PERSON, {})
    assert skip.calls == []


def test_findings_distinguish_missing_present_and_not_visible():
    payload = {"helmet": {"status": "MISSING"}, "vest": {"status": "DETECTED"}}
    f = build_findings(payload, {"head": True, "torso": True, "hands": True, "feet": False})
    assert f == [{"label": "helmet", "status": "MISSING"}, {"label": "vest", "status": "PRESENT"},
                 {"label": "boots", "status": "NOT_VISIBLE"}]          # luvas: câmera vê as mãos e nada foi observado -> sem conclusão
    assert build_findings({}, None) == []


def test_attach_sends_findings():
    inc = _Inc()
    inc.upload_evidence = lambda iid, jpeg, dets, findings=None: inc.calls.append((iid, findings)) or True
    _pipe(inc)._attach_evidence("INC-9", _frame(), PERSON, {"helmet": {"status": "MISSING"}}, {"head": True})
    assert inc.calls[0][1] == [{"label": "helmet", "status": "MISSING"}]


def _dark():
    return np.full((480, 640, 3), 15, dtype=np.uint8)


def test_dark_frame_is_not_used_as_evidence_and_a_good_one_replaces_it():
    """Webcam ainda ajustando a luz: o quadro escuro não vira prova; o próximo quadro bom, sim."""
    inc, pipe = _Inc(), None
    pipe = _pipe(inc)
    pipe._attach_evidence("INC-1", _dark(), PERSON, {})
    assert inc.calls == [] and pipe._evidence_pending == {"INC-1": 1}      # esperando
    pipe._attach_evidence("INC-1", _dark(), PERSON, {})
    assert inc.calls == [] and pipe._evidence_pending == {"INC-1": 2}
    pipe._attach_evidence("INC-1", _frame(), PERSON, {})                    # quadro com luz
    assert len(inc.calls) == 1 and pipe._evidence_pending == {}


def test_dark_frame_is_accepted_after_the_retry_limit_so_there_is_always_some_evidence():
    from app.camera_pipeline import EVIDENCE_MAX_RETRIES
    inc = _Inc()
    pipe = _pipe(inc)
    pipe._evidence_pending["INC-1"] = EVIDENCE_MAX_RETRIES
    pipe._attach_evidence("INC-1", _dark(), PERSON, {})
    assert len(inc.calls) == 1 and pipe._evidence_pending == {}


def test_after_the_limit_the_brightest_frame_seen_is_sent_not_the_last_one():
    from app.camera_pipeline import EVIDENCE_MAX_RETRIES
    import cv2
    inc = _Inc()
    pipe = _pipe(inc)
    mid = np.full((480, 640, 3), 30, dtype=np.uint8)       # abaixo de 45, mas o mais claro dos escuros
    pipe._attach_evidence("INC-1", np.full((480, 640, 3), 10, dtype=np.uint8), PERSON, {})
    pipe._attach_evidence("INC-1", mid, PERSON, {})
    pipe._attach_evidence("INC-1", np.full((480, 640, 3), 5, dtype=np.uint8), PERSON, {})
    pipe._evidence_pending["INC-1"] = EVIDENCE_MAX_RETRIES
    pipe._attach_evidence("INC-1", np.full((480, 640, 3), 8, dtype=np.uint8), PERSON, {})   # acabou a espera
    assert len(inc.calls) == 1 and pipe._evidence_best == {}
    # o enviado é o de brilho 30 (recorte reconstruído do mesmo tamanho; confere pela média do JPEG)
    img = cv2.imdecode(np.frombuffer(inc.last_jpeg, np.uint8), cv2.IMREAD_COLOR)
    assert 25 <= img.mean() <= 35, img.mean()

"""Cabeça/pés cortados pelo enquadramento -> 'não observável', nunca 'ausente'."""
from __future__ import annotations

from types import SimpleNamespace

from app.camera_pipeline import RealCameraPipeline
from app.observation_builder import build_fusion_ppe, regions_cut_by_frame

W, H = 640.0, 480.0


def test_bbox_touching_top_cuts_head_and_face():
    assert regions_cut_by_frame([100, 0, 300, 400], W, H) == {"head": False, "face": False}
    assert regions_cut_by_frame([100, 3, 300, 400], W, H) == {"head": False, "face": False}  # ~0,6%


def test_bbox_touching_bottom_cuts_feet():
    assert regions_cut_by_frame([100, 50, 300, 480], W, H) == {"feet": False}


def test_fully_inside_cuts_nothing():
    assert regions_cut_by_frame([100, 40, 300, 400], W, H) == {}


def test_bad_inputs_are_safe():
    assert regions_cut_by_frame(None, W, H) == {}
    assert regions_cut_by_frame([1, 2, 3], W, H) == {}
    assert regions_cut_by_frame([0, 0, 1, 1], 0, 0) == {}


def test_cut_head_omits_helmet_instead_of_missing():
    person = {"person_confidence": 0.9, "detections": [{"type": "SAFETY_VEST", "confidence": 0.93}]}
    cut = regions_cut_by_frame([100, 0, 300, 400], W, H)
    ppe = build_fusion_ppe(person, camera_can_see=cut)
    assert "helmet" not in ppe                      # não afirma ausência
    assert ppe["vest"]["status"] == "DETECTED"


def test_helmet_still_detected_even_when_head_is_cut():
    person = {"person_confidence": 0.9, "detections": [{"type": "HELMET", "confidence": 0.9}]}
    ppe = build_fusion_ppe(person, camera_can_see={"head": False})
    assert ppe["helmet"]["status"] == "DETECTED"


# ---- ponta a ponta no pipeline (clientes falsos) ----
class _Vision:
    def __init__(self, bbox):
        self.bbox = bbox

    def process_frame_image(self, camera_id, frame):
        return {"persons": [{"person_track_id": "T", "employee_id": None, "person_confidence": 0.9,
                             "person_bbox": self.bbox, "detections": []}]}


class _Id:
    def match(self, **kw):
        return {"status": "MATCHED", "employee_id": "FUNC-000001", "confidence": 0.97}


class _Fus:
    def __init__(self):
        self.sent = []

    def ingest(self, **kw):
        self.sent.append(kw["ppe"])
        return {}

    def get_employee_state(self, e):
        return {"employee_id": e, "identity_status": "MATCHED", "ppe": {}}


class _Rul:
    def evaluate(self, **kw):
        return {"overall_status": "INDETERMINATE", "violations": [], "evaluation_id": "E"}


class _Inc:
    def process_evaluation(self, ev):
        return []


def _run(bbox):
    fus = _Fus()
    pipe = RealCameraPipeline(_Vision(bbox), _Id(), fus, _Rul(), _Inc(), process_every_n_frames=1,
                              use_real_images=True)
    frame = SimpleNamespace(shape=(480, 640, 3))
    pipe.process_frame("CAM", frame)
    return fus.sent[-1]


def test_pipeline_cut_head_does_not_report_missing_helmet():
    ppe = _run([100, 0, 300, 400])
    assert "helmet" not in ppe and ppe["vest"]["status"] == "MISSING"


def test_pipeline_visible_head_still_reports_missing_helmet():
    ppe = _run([100, 60, 300, 400])
    assert ppe["helmet"]["status"] == "MISSING"


def test_real_services_omitted_helmet_is_not_a_violation(fusion, rules, incident):
    """Fusion + Rules + Incident REAIS: capacete omitido (cabeça cortada) não
    vira MISSING, não gera violação e não abre incidente."""
    from app.bridge import build_rules_evaluate_payload, enrich_violations_with_cameras

    emp = "FUNC-CUT-0001"
    fusion.ingest(camera_id="CAM-CUT", person_track_id="T", employee_id=emp,
                  ppe={"vest": {"status": "DETECTED", "confidence": 0.93}})
    state = fusion.get_employee_state(emp)
    assert state["ppe"]["helmet"]["status"] in ("NOT_OBSERVED", "NOT_VISIBLE")
    payload = build_rules_evaluate_payload(state)
    ev = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    assert ev["overall_status"] != "NON_COMPLIANT"
    assert not [v for v in ev["violations"] if v["ppe_type"] == "helmet"]
    incident.process_evaluation(enrich_violations_with_cameras(ev, state))
    assert incident.list(employee_id=emp) == []

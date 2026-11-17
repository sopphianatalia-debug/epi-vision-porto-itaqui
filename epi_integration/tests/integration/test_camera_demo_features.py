"""
Testes das novidades desta rodada da Fase 3.7 — DEMO_SCENARIO e o
roteamento para imagem real (`use_real_images`). Não sobem nenhum serviço:
usam um `FakeVisionClient` em memória, então rodam em milissegundos.
"""
from __future__ import annotations

from app.camera_config import resolve_demo_scenario_override
from app.camera_pipeline import RealCameraPipeline


class FakeVisionClient:
    """Dublê de VisionClient — grava qual método foi chamado e com o quê,
    sem fazer nenhuma chamada de rede de verdade."""

    def __init__(self, persons: list[dict]) -> None:
        self._persons = persons
        self.calls: list[tuple[str, str, object]] = []  # (method, camera_id, frame)

    def process_frame(self, camera_id: str, frame: dict) -> dict:
        self.calls.append(("process_frame", camera_id, frame))
        return {"camera_id": camera_id, "timestamp": "2026-01-01T00:00:00Z", "persons": self._persons}

    def process_frame_image(self, camera_id: str, image) -> dict:
        self.calls.append(("process_frame_image", camera_id, image))
        return {"camera_id": camera_id, "timestamp": "2026-01-01T00:00:00Z", "persons": self._persons}


class FakeDownstream:
    """Dublê mínimo para identity/fusion/rules/incident — só o suficiente
    para o pipeline não quebrar; os testes aqui são sobre o ROTEAMENTO de
    frame (dict vs imagem) e o override de demo, não sobre a lógica de
    negócio (essa já está coberta em test_camera_pipeline.py)."""

    def match(self, **kwargs):
        return {"status": "UNKNOWN", "employee_id": None, "confidence": None}

    def ingest(self, **kwargs):
        self.last_ingest = kwargs
        return {"employee_id": kwargs.get("employee_id"), "kind": "anonymous"}

    def get_employee_state(self, employee_id):
        return None

    def evaluate(self, **kwargs):
        return {"overall_status": "NOT_EVALUATED", "violations": [], "evaluation_id": "EVAL-FAKE"}

    def process_evaluation(self, evaluation):
        return []


PERSON = {
    "person_track_id": "TRACK-000001", "employee_id": None, "person_confidence": 0.9,
    "person_bbox": [0, 0, 10, 10], "detections": [],
}


# --------------------------------------------------------------------- #
# use_real_images — roteamento dict vs imagem
# --------------------------------------------------------------------- #
def test_default_uses_process_frame_with_dict():
    vision = FakeVisionClient([PERSON])
    downstream = FakeDownstream()
    pipe = RealCameraPipeline(vision, downstream, downstream, downstream, downstream, process_every_n_frames=1)

    scene = {"detections": []}
    pipe.process_frame("CAM-01", scene)

    assert len(vision.calls) == 1
    method, camera_id, frame = vision.calls[0]
    assert method == "process_frame"
    assert frame is scene


def test_use_real_images_true_calls_process_frame_image():
    vision = FakeVisionClient([PERSON])
    downstream = FakeDownstream()
    pipe = RealCameraPipeline(vision, downstream, downstream, downstream, downstream,
                               process_every_n_frames=1, use_real_images=True)

    fake_image = object()  # não precisa ser um array de verdade para este teste de roteamento
    pipe.process_frame("CAM-01", fake_image)

    assert len(vision.calls) == 1
    method, camera_id, frame = vision.calls[0]
    assert method == "process_frame_image"
    assert frame is fake_image


# --------------------------------------------------------------------- #
# resolve_demo_scenario_override
# --------------------------------------------------------------------- #
def test_resolve_demo_scenario_empty_is_none():
    assert resolve_demo_scenario_override("") is None


def test_resolve_demo_scenario_unknown_value_is_none_not_error():
    # Um typo na env var não deve travar a demo — só fica sem efeito.
    assert resolve_demo_scenario_override("missing_shoes_typo") is None


def test_resolve_demo_scenario_missing_helmet():
    override = resolve_demo_scenario_override("missing_helmet")
    assert override == {"helmet": {"status": "MISSING", "confidence": 0.95}}


def test_resolve_demo_scenario_all_four_types_covered():
    for scenario, ppe_type in [
        ("missing_helmet", "helmet"), ("missing_vest", "vest"),
        ("missing_gloves", "gloves"), ("missing_boots", "boots"),
    ]:
        override = resolve_demo_scenario_override(scenario)
        assert ppe_type in override
        assert override[ppe_type]["status"] == "MISSING"


# --------------------------------------------------------------------- #
# demo_ppe_override no RealCameraPipeline — aplicado sobre a detecção real
# --------------------------------------------------------------------- #
def test_demo_ppe_override_forces_missing_on_top_of_real_detection():
    # A "detecção real" (fake) diz que o capacete FOI detectado — o override
    # de demo deve sobrescrever isso, deliberadamente, para fins de demo.
    person_with_helmet = {
        "person_track_id": "TRACK-000001", "employee_id": None, "person_confidence": 0.9,
        "person_bbox": [0, 0, 10, 10],
        "detections": [{"type": "HELMET", "confidence": 0.96, "bbox": [1, 1, 5, 5]}],
    }
    vision = FakeVisionClient([person_with_helmet])
    downstream = FakeDownstream()
    pipe = RealCameraPipeline(
        vision, downstream, downstream, downstream, downstream,
        process_every_n_frames=1,
        demo_ppe_override={"helmet": {"status": "MISSING", "confidence": 0.95}},
    )

    pipe.process_frame("CAM-01", {"detections": []})

    # O que foi de fato enviado ao Fusion (via downstream.ingest) precisa
    # refletir o override, não a detecção real.
    assert downstream.last_ingest["ppe"]["helmet"]["status"] == "MISSING"


def test_no_demo_override_by_default_keeps_real_detection():
    person_with_helmet = {
        "person_track_id": "TRACK-000001", "employee_id": None, "person_confidence": 0.9,
        "person_bbox": [0, 0, 10, 10],
        "detections": [{"type": "HELMET", "confidence": 0.96, "bbox": [1, 1, 5, 5]}],
    }
    vision = FakeVisionClient([person_with_helmet])
    downstream = FakeDownstream()
    pipe = RealCameraPipeline(vision, downstream, downstream, downstream, downstream, process_every_n_frames=1)

    pipe.process_frame("CAM-01", {"detections": []})

    assert downstream.last_ingest["ppe"]["helmet"]["status"] == "DETECTED"


def test_skipped_frames_are_flagged_not_treated_as_zero_people():
    """Com process_every_n_frames=N, N-1 de cada N frames voltam [] sem
    significar 'ninguém na câmera'. A flag permite à tela manter o último
    resultado (antes mostrava 'Pessoas: 0' em ~80% dos frames)."""
    from app.camera_pipeline import RealCameraPipeline

    class _Dummy:
        def __getattr__(self, name):
            raise AssertionError("não deveria chamar serviços em frame pulado")

    pipe = RealCameraPipeline.__new__(RealCameraPipeline)
    pipe.metrics = type("M", (), {"frames_received": 0})()
    pipe._frame_index = 0
    pipe._every_n = 5
    pipe.last_frame_processed = True
    assert pipe.process_frame("CAM", object()) == []
    assert pipe.last_frame_processed is False


class _TwoPersonsVision:
    def __init__(self, conf_a=0.9, conf_b=0.7):
        self.conf = {"TRK-A": conf_a, "TRK-B": conf_b}

    def process_frame(self, camera_id, frame):
        return {"persons": [
            {"person_track_id": t, "employee_id": None, "person_confidence": c,
             "person_bbox": [0, 0, 10, 10], "detections": []}
            for t, c in self.conf.items()]}


class _Id:
    def match(self, camera_id, seed, person_track_id):
        return {"status": "MATCHED", "employee_id": "FUNC-000001", "confidence": 0.97}


class _Fus:
    def ingest(self, **kw):
        return {}

    def get_employee_state(self, employee_id):
        return {"employee_id": employee_id, "identity_status": "MATCHED", "ppe": {}}


class _Rul:
    def __init__(self):
        self.employees = []

    def evaluate(self, **kw):
        self.employees.append(kw["employee_id"])
        return {"overall_status": "COMPLIANT", "violations": [], "evaluation_id": "E"}


class _Inc:
    def process_evaluation(self, evaluation):
        return []


def _two_person_pipe(vision, single):
    from app.camera_pipeline import RealCameraPipeline
    rules = _Rul()
    pipe = RealCameraPipeline(vision, _Id(), _Fus(), rules, _Inc(), process_every_n_frames=1,
                              identity_seed_provider=lambda c, t: "FUNC-000001",
                              single_identity_per_frame=single)
    return pipe, rules


def test_demo_identity_goes_only_to_most_confident_person():
    pipe, rules = _two_person_pipe(_TwoPersonsVision(), single=True)
    res = {r.person_track_id: r for r in pipe.process_frame("CAM", {})}
    assert res["TRK-A"].employee_id == "FUNC-000001"
    assert res["TRK-B"].employee_id is None and res["TRK-B"].identity_status == "UNKNOWN"
    assert rules.employees.count("FUNC-000001") == 1          # a fantasma nem é avaliada


def test_primary_identity_is_sticky_while_present():
    vision = _TwoPersonsVision()
    pipe, _ = _two_person_pipe(vision, single=True)
    pipe.process_frame("CAM", {})
    vision.conf = {"TRK-A": 0.7, "TRK-B": 0.8}                # B um pouco melhor: não troca
    res = {r.person_track_id: r for r in pipe.process_frame("CAM", {})}
    assert res["TRK-A"].employee_id == "FUNC-000001"          # A continua principal
    assert res["TRK-B"].employee_id is None


def test_primary_yields_to_clearly_better_person():
    vision = _TwoPersonsVision(conf_a=0.66, conf_b=0.2)       # A (fantasma) chegou primeiro
    pipe, _ = _two_person_pipe(vision, single=True)
    pipe.process_frame("CAM", {})
    vision.conf = {"TRK-A": 0.66, "TRK-B": 0.93}              # chega o trabalhador de verdade
    res = {r.person_track_id: r for r in pipe.process_frame("CAM", {})}
    assert res["TRK-B"].employee_id == "FUNC-000001"
    assert res["TRK-A"].employee_id is None


def test_default_behaviour_unchanged_without_flag():
    pipe, _ = _two_person_pipe(_TwoPersonsVision(), single=False)
    res = pipe.process_frame("CAM", {})
    assert all(r.employee_id == "FUNC-000001" for r in res)

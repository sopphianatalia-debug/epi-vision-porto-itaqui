from app.enums import PPEStatus
from app.evaluators import evaluate_frame
from app.pose import HeuristicPose
from app.visibility import VisibilityAnalyzer
from tests.conftest import default_settings, full_body_obs, ppe


def run(obs):
    s = default_settings()
    pose = HeuristicPose()
    regions = pose.regions(obs.person_bbox)
    vis = VisibilityAnalyzer(pose, s.frame_edge_margin).analyze(obs)
    return evaluate_frame(obs, regions, vis, s)


def test_helmet_on_head_is_proper():
    obs = full_body_obs(ppe_list=[ppe("helmet", 360, 110, 440, 180)])
    assert run(obs)["helmet"].status == PPEStatus.PROPER


def test_helmet_in_hand_is_improper():
    # Capacete na altura da mão direita, longe da cabeça.
    obs = full_body_obs(ppe_list=[ppe("helmet", 440, 470, 500, 540)])
    assert run(obs)["helmet"].status == PPEStatus.IMPROPER


def test_helmet_absent_is_missing_when_head_visible():
    obs = full_body_obs(ppe_list=[])
    assert run(obs)["helmet"].status == PPEStatus.MISSING


def test_vest_covering_torso_is_proper():
    obs = full_body_obs(ppe_list=[ppe("vest", 325, 270, 475, 520)])
    assert run(obs)["vest"].status == PPEStatus.PROPER


def test_boots_not_visible_when_feet_cut_off():
    # Câmera de torso: pés fora de quadro -> NOT_VISIBLE, jamais MISSING.
    from app.types import PersonObservation
    from tests.conftest import bbox
    obs = PersonObservation("T1", bbox(300, 100, 500, 600), 1000, 600, ppe=[])
    assert run(obs)["boots"].status == PPEStatus.NOT_VISIBLE


def test_gloves_left_present_right_missing():
    obs = full_body_obs(ppe_list=[ppe("gloves", 310, 470, 360, 520)])  # só mão esquerda
    out = run(obs)
    assert out["glove_left"].status == PPEStatus.PROPER
    assert out["glove_right"].status == PPEStatus.MISSING

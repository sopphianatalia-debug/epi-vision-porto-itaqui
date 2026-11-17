from app.enums import BodyRegion, Visibility
from app.pose import HeuristicPose
from app.visibility import VisibilityAnalyzer
from tests.conftest import bbox
from app.types import PersonObservation


def analyzer():
    return VisibilityAnalyzer(HeuristicPose(), edge_margin=0.01)


def full_body(frame=(1000, 1000)):
    return PersonObservation("T1", bbox(300, 100, 500, 900), frame[0], frame[1])


def torso_only():
    # Pessoa cortada embaixo (frame de 600 de altura): pés/pernas não visíveis.
    return PersonObservation("T1", bbox(300, 100, 500, 600), 1000, 600)


def test_full_body_all_visible():
    vis = analyzer().analyze(full_body())
    assert vis[BodyRegion.HEAD] == Visibility.VISIBLE
    assert vis[BodyRegion.FEET] == Visibility.VISIBLE
    assert vis[BodyRegion.TORSO] == Visibility.VISIBLE


def test_torso_camera_hides_feet():
    vis = analyzer().analyze(torso_only())
    assert vis[BodyRegion.TORSO] == Visibility.VISIBLE
    assert vis[BodyRegion.FEET] == Visibility.NOT_VISIBLE  # regra central do spec


def test_head_cut_off_top():
    obs = PersonObservation("T1", bbox(300, 0, 500, 700), 1000, 1000)
    vis = analyzer().analyze(obs)
    assert vis[BodyRegion.HEAD] == Visibility.NOT_VISIBLE


def test_explicit_visibility_override():
    obs = PersonObservation(
        "T1", bbox(300, 100, 500, 900), 1000, 1000,
        visible_regions={BodyRegion.FEET: Visibility.NOT_VISIBLE},
    )
    vis = analyzer().analyze(obs)
    assert vis[BodyRegion.FEET] == Visibility.NOT_VISIBLE
    assert vis[BodyRegion.HEAD] == Visibility.NOT_VISIBLE  # não informado -> não visível

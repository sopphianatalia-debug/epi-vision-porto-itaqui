from app.domain.enums import BodyRegionKey, PPEStatus, PPEType
from app.domain.models import CameraVisibilityProfile
from tests.conftest import make_service, obs


def test_three_cameras_same_employee_consolidate():
    svc, _clk, _bus = make_service()
    svc.ingest_observation(obs("CAM-01", "TRACK-001", "FUNC-000234",
                               {"helmet": ("DETECTED", 0.95), "vest": ("DETECTED", 0.96)}))
    svc.ingest_observation(obs("CAM-03", "TRACK-017", "FUNC-000234", {"gloves": ("DETECTED", 0.91)}))
    svc.ingest_observation(obs("CAM-07", "TRACK-083", "FUNC-000234", {"boots": ("DETECTED", 0.93)}))

    state = svc.get_employee_state("FUNC-000234")
    assert state.ppe[PPEType.HELMET].status == PPEStatus.DETECTED
    assert state.ppe[PPEType.VEST].status == PPEStatus.DETECTED
    assert state.ppe[PPEType.GLOVES].status == PPEStatus.DETECTED
    assert state.ppe[PPEType.BOOTS].status == PPEStatus.DETECTED
    assert set(state.cameras.keys()) == {"CAM-01", "CAM-03", "CAM-07"}


def test_different_tracks_same_employee_grouped_by_employee():
    svc, _clk, _bus = make_service()
    svc.ingest_observation(obs("CAM-01", "TRACK-001", "FUNC-000234", {"helmet": ("DETECTED", 0.95)}))
    svc.ingest_observation(obs("CAM-03", "TRACK-017", "FUNC-000234", {"vest": ("DETECTED", 0.9)}))
    state = svc.get_employee_state("FUNC-000234")
    # tracks diferentes, mesmo funcionário
    assert state.cameras["CAM-01"].track_id == "TRACK-001"
    assert state.cameras["CAM-03"].track_id == "TRACK-017"


def test_agreeing_cameras_boost_confidence():
    svc, _clk, _bus = make_service()
    svc.ingest_observation(obs("CAM-01", "T1", "FUNC-000234", {"helmet": ("DETECTED", 0.8)}))
    svc.ingest_observation(obs("CAM-02", "T2", "FUNC-000234", {"helmet": ("DETECTED", 0.8)}))
    state = svc.get_employee_state("FUNC-000234")
    # noisy-OR: duas câmeras a 0.8 -> confiança > 0.8 (não é média)
    assert state.ppe[PPEType.HELMET].confidence > 0.8


def test_camera_without_visibility_yields_not_visible_not_missing():
    svc, _clk, _bus = make_service()
    # CAM-01 só vê a parte de cima; não enxerga botas.
    svc.set_visibility_profile(CameraVisibilityProfile("CAM-01", {
        BodyRegionKey.HEAD: True, BodyRegionKey.TORSO: True,
        BodyRegionKey.HANDS: True, BodyRegionKey.FEET: False, BodyRegionKey.FACE: True,
    }))
    svc.ingest_observation(obs("CAM-01", "T1", "FUNC-000234",
                               {"helmet": ("DETECTED", 0.95), "vest": ("DETECTED", 0.9)}))
    state = svc.get_employee_state("FUNC-000234")
    assert state.ppe[PPEType.BOOTS].status == PPEStatus.NOT_VISIBLE  # nunca MISSING


def test_explicit_missing_from_visible_camera_is_missing():
    svc, _clk, _bus = make_service()
    svc.set_visibility_profile(CameraVisibilityProfile("CAM-05", {
        BodyRegionKey.HEAD: True, BodyRegionKey.TORSO: True,
        BodyRegionKey.HANDS: True, BodyRegionKey.FEET: True, BodyRegionKey.FACE: True,
    }))
    svc.ingest_observation(obs("CAM-05", "T1", "FUNC-000234",
                               {"helmet": ("DETECTED", 0.9), "boots": ("MISSING", 0.85)}))
    state = svc.get_employee_state("FUNC-000234")
    assert state.ppe[PPEType.BOOTS].status == PPEStatus.MISSING


def test_conflict_proper_vs_improper_unresolved_becomes_unknown():
    svc, _clk, _bus = make_service(settings=None)
    # PROPER 0.91 vs IMPROPER 0.88 -> diferença 0.03 < margem 0.15 -> UNKNOWN + conflito
    svc.ingest_observation(obs("CAM-01", "T1", "FUNC-000234", {"helmet": ("PROPER", 0.91)}))
    svc.ingest_observation(obs("CAM-02", "T2", "FUNC-000234", {"helmet": ("IMPROPER", 0.88)}))
    state = svc.get_employee_state("FUNC-000234")
    assert state.ppe[PPEType.HELMET].status == PPEStatus.UNKNOWN
    assert state.ppe[PPEType.HELMET].conflict is True
    assert svc.get_conflicts()  # registrado

from app.domain.enums import FusionStatus, PPEStatus, PPEType
from tests.conftest import make_service, obs


def test_integration_three_cameras_one_employee():
    """CAM-01 (capacete+colete) + CAM-03 (luvas) + CAM-07 (botas) -> tudo DETECTED."""
    svc, _clk, bus = make_service()

    svc.ingest_observation(obs("CAM-01", "TRACK-001", "FUNC-000234",
                               {"helmet": ("DETECTED", 0.95), "vest": ("DETECTED", 0.96)}))
    svc.ingest_observation(obs("CAM-03", "TRACK-017", "FUNC-000234", {"gloves": ("DETECTED", 0.91)}))
    svc.ingest_observation(obs("CAM-07", "TRACK-083", "FUNC-000234", {"boots": ("DETECTED", 0.93)}))

    state = svc.get_employee_state("FUNC-000234")
    assert state.overall_status == FusionStatus.COMPLETE
    for ppe in (PPEType.HELMET, PPEType.VEST, PPEType.GLOVES, PPEType.BOOTS):
        assert state.ppe[ppe].status == PPEStatus.DETECTED

    # e a câmera sem rosto (employee_id null) não é atribuída
    r = svc.ingest_observation(obs("CAM-07", "TRACK-089", employee=None, ppe={"boots": ("DETECTED", 0.94)}))
    assert r.employee_id is None
    assert svc.get_anonymous_observations()  # ficou como observação anônima

    # eventos emitidos ao longo do fluxo
    types = {e["type"] for e in bus.recent()}
    assert "FUSION_CREATED" in types
    assert "ANONYMOUS_OBSERVATION" in types

from app.domain.enums import IdentityStatus, PPEStatus, PPEType
from tests.conftest import T0, make_service, obs


def test_old_observation_outside_window_is_ignored():
    svc, clk, _bus = make_service(settings=None)
    # observação "antiga" (10s atrás), janela de 5s
    svc.ingest_observation(obs("CAM-01", "T1", "FUNC-000234", {"helmet": ("DETECTED", 0.9)}, ts=T0))
    clk.advance(10)
    # nova observação só com colete
    svc.ingest_observation(obs("CAM-02", "T2", "FUNC-000234", {"vest": ("DETECTED", 0.9)},
                               ts=clk.now()))
    state = svc.get_employee_state("FUNC-000234")
    # capacete antigo saiu da janela -> não é DETECTED agora
    assert state.ppe[PPEType.HELMET].status != PPEStatus.DETECTED
    assert state.ppe[PPEType.VEST].status == PPEStatus.DETECTED


def test_last_known_identity_within_ttl():
    svc, clk, _bus = make_service()
    # MATCHED agora
    svc.ingest_observation(obs("CAM-01", "TRACK-001", "FUNC-000234",
                               {"helmet": ("DETECTED", 0.95)}, ts=clk.now()))
    clk.advance(2)  # < identity_ttl (3s)
    # rosto sumiu: mesma câmera+track, sem MATCH -> mantém a identidade
    r = svc.ingest_observation(obs("CAM-01", "TRACK-001", employee=None,
                                   ppe={"vest": ("DETECTED", 0.9)},
                                   identity="NOT_IDENTIFIED", ts=clk.now()))
    assert r.employee_id == "FUNC-000234"
    assert r.reason == "last_known"


def test_last_known_identity_expires_after_ttl():
    svc, clk, _bus = make_service()
    svc.ingest_observation(obs("CAM-01", "TRACK-001", "FUNC-000234",
                               {"helmet": ("DETECTED", 0.95)}, ts=clk.now()))
    clk.advance(5)  # > identity_ttl (3s)
    r = svc.ingest_observation(obs("CAM-01", "TRACK-001", employee=None,
                                   ppe={"vest": ("DETECTED", 0.9)},
                                   identity="NOT_IDENTIFIED", ts=clk.now()))
    assert r.employee_id is None  # virou anônimo


def test_state_expires_after_timeout():
    svc, clk, _bus = make_service()
    svc.ingest_observation(obs("CAM-01", "T1", "FUNC-000234", {"helmet": ("DETECTED", 0.95)}, ts=clk.now()))
    assert svc.get_employee_state("FUNC-000234") is not None
    clk.advance(40)  # > state_ttl (30s)
    expired = svc.expire_stale_state()
    assert "FUNC-000234" in expired
    assert svc.get_employee_state("FUNC-000234") is None

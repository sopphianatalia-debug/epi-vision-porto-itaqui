from app.domain.enums import IdentityStatus
from tests.conftest import make_service, obs


def test_matched_valid_active_is_joinable():
    svc, _clk, _bus = make_service()
    r = svc.ingest_observation(obs("CAM-01", "TRACK-001", "FUNC-000234",
                                    {"helmet": ("DETECTED", 0.95)}))
    assert r.kind == "employee_state"
    assert r.employee_id == "FUNC-000234"


def test_no_employee_id_is_anonymous():
    svc, _clk, _bus = make_service()
    r = svc.ingest_observation(obs("CAM-07", "TRACK-083", employee=None,
                                    ppe={"boots": ("DETECTED", 0.94)}))
    assert r.kind == "anonymous"
    assert r.employee_id is None
    assert r.identity_status == IdentityStatus.NOT_IDENTIFIED


def test_low_confidence_is_not_joined():
    svc, _clk, _bus = make_service()
    r = svc.ingest_observation(obs("CAM-01", "T1", "FUNC-000234",
                                    {"helmet": ("DETECTED", 0.9)}, conf=0.5))
    assert r.kind == "anonymous"


def test_ambiguous_identity_is_not_joined():
    svc, _clk, _bus = make_service()
    r = svc.ingest_observation(obs("CAM-01", "T1", "FUNC-000234",
                                    {"helmet": ("DETECTED", 0.9)}, identity="AMBIGUOUS"))
    assert r.kind == "anonymous"


def test_invalid_employee_id_rejected():
    svc, _clk, _bus = make_service()
    r = svc.ingest_observation(obs("CAM-01", "T1", "FUNC-999999",
                                    {"helmet": ("DETECTED", 0.9)}))
    assert r.kind == "anonymous"
    assert r.reason == "invalid_employee_id"


def test_inactive_employee_id_rejected():
    from app.identity import InMemoryEmployeeDirectory
    directory = InMemoryEmployeeDirectory(active=set(), inactive={"FUNC-000234"})
    svc, _clk, _bus = make_service(directory=directory)
    r = svc.ingest_observation(obs("CAM-01", "T1", "FUNC-000234",
                                    {"helmet": ("DETECTED", 0.9)}))
    assert r.kind == "anonymous"
    assert r.reason == "inactive_employee_id"


def test_anonymous_not_attributed_even_if_employee_present_elsewhere():
    # FUNC-000234 identificado na CAM-01; pessoa anônima na CAM-07 NÃO herda a identidade.
    svc, _clk, _bus = make_service()
    svc.ingest_observation(obs("CAM-01", "TRACK-001", "FUNC-000234", {"helmet": ("DETECTED", 0.95)}))
    r = svc.ingest_observation(obs("CAM-07", "TRACK-083", employee=None, ppe={"boots": ("DETECTED", 0.94)}))
    assert r.employee_id is None
    state = svc.get_employee_state("FUNC-000234")
    # o estado do funcionário não recebeu as botas da observação anônima
    from app.domain.enums import PPEStatus, PPEType
    assert state.ppe[PPEType.BOOTS].status != PPEStatus.DETECTED

"""Evidência de localização de EPI (tracker) no Fusion — fonte separada.

Garante: tracker não prova uso; divergência é POSSIBLE_INCONSISTENCY (não
violação); localização expirada/antiga não afirma nada; a consolidação por
câmera não é alterada.
"""
from app.domain.enums import PPEStatus, PPEType
from app.ppe_location import PPELocationService
from tests.conftest import make_service, obs


def make(svc, clk, ttl=30.0):
    return PPELocationService(clk, svc.get_employee_state, ttl_seconds=ttl)


def tracker_payload(**over):
    base = {
        "source": "tracker", "tracker_id": "TRACKER-001", "ppe_id": "HELMET-001",
        "ppe_type": "helmet", "employee_id_assigned": "FUNC-000234",
        "area_id": "PATIO-02", "location_state": "CURRENT", "confidence": 0.94,
        "timestamp": "2026-08-12T15:30:00+00:00",
    }
    base.update(over)
    return base


def seed_camera_sees_helmet(svc, clk, loc):
    svc.ingest_observation(obs("CAM-ENTRY-02", "T1", "FUNC-000234",
                               {"helmet": ("DETECTED", 0.96)}, ts=clk.now()))
    loc.set_camera_area("CAM-ENTRY-02", "PATIO-02")


def test_ingest_keeps_latest_per_tracker_and_never_claims_usage():
    svc, clk, _ = make_service()
    loc = make(svc, clk)
    loc.ingest(tracker_payload(area_id="PATIO-01"))
    loc.ingest(tracker_payload(area_id="PATIO-02"))
    ev = loc.evidence_for_employee("FUNC-000234")
    assert len(ev) == 1 and ev[0].area_id == "PATIO-02"
    assert loc.employee_view("FUNC-000234")["ppe_locations"][0]["proves_usage"] is False


def test_ingest_requires_tracker_id_and_valid_confidence():
    svc, clk, _ = make_service()
    loc = make(svc, clk)
    for bad in ({"tracker_id": ""}, {"confidence": 1.5}):
        try:
            loc.ingest(tracker_payload(**bad))
            assert False, "deveria falhar"
        except ValueError:
            pass


def test_same_area_no_inconsistency():
    svc, clk, _ = make_service()
    loc = make(svc, clk)
    seed_camera_sees_helmet(svc, clk, loc)
    loc.ingest(tracker_payload(area_id="PATIO-02"))
    assert loc.inconsistencies_for_employee("FUNC-000234") == []


def test_different_area_is_possible_inconsistency_not_violation():
    svc, clk, _ = make_service()
    loc = make(svc, clk)
    seed_camera_sees_helmet(svc, clk, loc)
    loc.ingest(tracker_payload(area_id="ARMAZEM"))
    items = loc.inconsistencies_for_employee("FUNC-000234")
    assert len(items) == 1
    assert items[0]["type"] == "POSSIBLE_INCONSISTENCY"
    assert items[0]["is_violation"] is False
    assert items[0]["camera_area_id"] == "PATIO-02" and items[0]["tracker_area_id"] == "ARMAZEM"


def test_expired_location_asserts_nothing():
    svc, clk, _ = make_service()
    loc = make(svc, clk)
    seed_camera_sees_helmet(svc, clk, loc)
    loc.ingest(tracker_payload(area_id="ARMAZEM", location_state="EXPIRED"))
    assert loc.inconsistencies_for_employee("FUNC-000234") == []


def test_stale_evidence_asserts_nothing():
    svc, clk, _ = make_service()
    loc = make(svc, clk, ttl=10.0)
    seed_camera_sees_helmet(svc, clk, loc)
    loc.ingest(tracker_payload(area_id="ARMAZEM"))
    clk.advance(11)
    assert loc.inconsistencies_for_employee("FUNC-000234") == []
    assert loc.employee_view("FUNC-000234")["ppe_locations"][0]["stale"] is True


def test_camera_did_not_see_ppe_no_comparison():
    svc, clk, _ = make_service()
    loc = make(svc, clk)
    svc.ingest_observation(obs("CAM-ENTRY-02", "T1", "FUNC-000234",
                               {"helmet": ("MISSING", 0.9)}, ts=clk.now()))
    loc.set_camera_area("CAM-ENTRY-02", "PATIO-02")
    loc.ingest(tracker_payload(area_id="ARMAZEM"))
    assert loc.inconsistencies_for_employee("FUNC-000234") == []


def test_camera_without_known_area_no_comparison():
    svc, clk, _ = make_service()
    loc = make(svc, clk)
    svc.ingest_observation(obs("CAM-X", "T1", "FUNC-000234",
                               {"helmet": ("DETECTED", 0.9)}, ts=clk.now()))
    loc.ingest(tracker_payload(area_id="ARMAZEM"))
    assert loc.inconsistencies_for_employee("FUNC-000234") == []


def test_tracker_evidence_does_not_change_camera_consolidation():
    svc, clk, _ = make_service()
    loc = make(svc, clk)
    svc.ingest_observation(obs("CAM-ENTRY-02", "T1", "FUNC-000234",
                               {"helmet": ("DETECTED", 0.96)}, ts=clk.now()))
    before = svc.get_employee_state("FUNC-000234").to_dict()
    loc.ingest(tracker_payload(ppe_type="gloves", ppe_id="GLOVES-001", tracker_id="TRACKER-009"))
    assert svc.get_employee_state("FUNC-000234").to_dict() == before
    assert svc.get_employee_state("FUNC-000234").ppe[PPEType.HELMET].status == PPEStatus.DETECTED


def test_goggles_maps_to_glasses_for_comparison():
    svc, clk, _ = make_service()
    loc = make(svc, clk)
    svc.ingest_observation(obs("CAM-ENTRY-02", "T1", "FUNC-000234",
                               {"glasses": ("DETECTED", 0.9)}, ts=clk.now()))
    loc.set_camera_area("CAM-ENTRY-02", "PATIO-02")
    loc.ingest(tracker_payload(ppe_type="goggles", ppe_id="GOG-1", tracker_id="T-G", area_id="ARMAZEM"))
    assert len(loc.inconsistencies_for_employee("FUNC-000234")) == 1


def test_unknown_employee_state_returns_empty():
    svc, clk, _ = make_service()
    loc = make(svc, clk)
    loc.ingest(tracker_payload(employee_id_assigned="FUNC-000111", area_id="ARMAZEM"))
    assert loc.inconsistencies_for_employee("FUNC-000111") == []

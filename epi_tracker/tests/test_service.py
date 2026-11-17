"""
Testes do TrackerService — cobrem os itens 1-24 da seção 36 do pedido.
Usam o `service` fixture (FakeClock, TTL controlável) em vez de HTTP, para
testar TTL/expiração com precisão sem depender de tempo real.
"""
from __future__ import annotations

import pytest

from app.domain.enums import (
    LocationState,
    ObservationStatus,
    PPEAssetStatus,
    PPEType,
    SafetyCheckStatus,
    TrackerStatus,
    TrackerTechnology,
)
from app.domain.models import TrackerAlreadyRegisteredError
from app.infrastructure.event_bus import EventType
from app.service import (
    AreaNotFoundError,
    CheckpointNotFoundError,
    PPEAssetNotFoundError,
    TrackerNotFoundError,
)


# 1) cadastro de tracker
def test_register_tracker(service):
    t = service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    assert t.tracker_id == "TRACKER-001"
    assert t.status == TrackerStatus.ACTIVE
    assert service.get_tracker("TRACKER-001") is t


def test_register_tracker_without_id_generates_one(service):
    t = service.register_tracker(TrackerTechnology.BLE)
    assert t.tracker_id.startswith("TRACKER-")


def test_register_duplicate_tracker_raises(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    with pytest.raises(TrackerAlreadyRegisteredError):
        service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")


# 2) cadastro de EPI
def test_register_ppe(service):
    ppe = service.register_ppe_asset(PPEType.HELMET)
    assert ppe.ppe_type == PPEType.HELMET
    assert ppe.status == PPEAssetStatus.REGISTERED
    assert ppe.employee_id is None


# 3) associação tracker -> EPI
def test_register_ppe_with_tracker(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    ppe = service.register_ppe_asset(PPEType.HELMET, tracker_id="TRACKER-001")
    assert ppe.tracker_id == "TRACKER-001"


def test_register_ppe_with_unknown_tracker_raises(service):
    with pytest.raises(TrackerNotFoundError):
        service.register_ppe_asset(PPEType.HELMET, tracker_id="TRACKER-999")


# 4) associação EPI -> funcionário (ASSIGNED != WORN, seção 16)
def test_assign_ppe_to_employee_is_not_proof_of_use(service):
    ppe = service.register_ppe_asset(PPEType.HELMET)
    updated = service.assign_ppe_to_employee(ppe.ppe_id, "FUNC-000234")
    assert updated.employee_id == "FUNC-000234"
    assert updated.status == PPEAssetStatus.ASSIGNED
    assert updated.assigned_at is not None
    # A associação em si NUNCA aparece como "uso confirmado" em nenhum campo
    # — não existe um campo tipo `worn=True` neste modelo, de propósito.


def test_assign_unknown_ppe_raises(service):
    with pytest.raises(PPEAssetNotFoundError):
        service.assign_ppe_to_employee("PPE-999", "FUNC-000234")


# 5) cadastro de área
def test_register_area(service):
    area = service.register_area("PATIO-02", "Pátio de Carga")
    assert area.area_id == "PATIO-02"
    assert service.get_area("PATIO-02") is area


def test_get_unknown_area_raises(service):
    with pytest.raises(AreaNotFoundError):
        service.get_area("AREA-INEXISTENTE")


# 6) cadastro de checkpoint
def test_register_checkpoint(service):
    service.register_area("PATIO-02", "Pátio 02")
    checkpoint = service.register_checkpoint("PATIO-02", "Entrada Pátio 02",
                                              checkpoint_id="CHECKPOINT-PATIO-02", camera_id="CAM-ENTRY-02")
    assert checkpoint.area_id == "PATIO-02"
    assert checkpoint.camera_id == "CAM-ENTRY-02"


def test_register_checkpoint_unknown_area_raises(service):
    with pytest.raises(AreaNotFoundError):
        service.register_checkpoint("AREA-X", "Checkpoint X")


# 7) cadastro de reader
def test_register_reader(service):
    service.register_area("PATIO-02", "Pátio 02")
    reader = service.register_reader("PATIO-02", TrackerTechnology.MOCK, reader_id="READER-02")
    assert reader.area_id == "PATIO-02"


# 8) observação de localização
def test_poll_provider_records_observation(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-01", "Pátio 01")
    service._provider.simulate_location("TRACKER-001", "PATIO-01")  # acesso direto ao provider do fixture

    obs = service.poll_provider("TRACKER-001")
    assert obs.area_id == "PATIO-01"
    assert obs.status == ObservationStatus.DETECTED


# 9) mudança de localização
def test_location_change_emits_entered_and_exited_events(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-01", "Pátio 01")
    service.register_area("PATIO-02", "Pátio 02")

    service._provider.simulate_location("TRACKER-001", "PATIO-01")
    service.poll_provider("TRACKER-001")
    service._provider.simulate_location("TRACKER-001", "PATIO-02")
    service.poll_provider("TRACKER-001")

    assert service._bus.count(EventType.TRACKER_EXITED_AREA) == 1
    assert service._bus.count(EventType.TRACKER_ENTERED_AREA) == 2


# 10) entrada em área (Safety Check + evento de funcionário)
def test_safety_check_emits_employee_entered_area(service):
    service.register_area("PATIO-02", "Pátio 02")
    service.register_checkpoint("PATIO-02", "Entrada", checkpoint_id="CHECKPOINT-1")

    service.record_safety_check("FUNC-000234", "PATIO-02", "CHECKPOINT-1", SafetyCheckStatus.COMPLIANT)

    assert service._bus.count(EventType.EMPLOYEE_ENTERED_AREA) == 1


# 11) saída de área (troca de área do funcionário)
def test_employee_moving_area_emits_exit_then_entry():
    from datetime import datetime, timezone
    from app.infrastructure.clock import FakeClock
    from app.infrastructure.event_bus import InMemoryEventBus
    from app.observability.metrics import TrackerMetrics
    from app.providers.mock_provider import MockTrackerProvider
    from app.service import TrackerService

    svc = TrackerService(FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc)), InMemoryEventBus(),
                          TrackerMetrics(), MockTrackerProvider())
    svc.register_area("PATIO-01", "Pátio 01")
    svc.register_area("PATIO-02", "Pátio 02")
    svc.register_checkpoint("PATIO-01", "Entrada 1", checkpoint_id="CK-1")
    svc.register_checkpoint("PATIO-02", "Entrada 2", checkpoint_id="CK-2")

    svc.record_safety_check("FUNC-000234", "PATIO-01", "CK-1", SafetyCheckStatus.COMPLIANT)
    svc.record_safety_check("FUNC-000234", "PATIO-02", "CK-2", SafetyCheckStatus.COMPLIANT)

    assert svc._bus.count(EventType.EMPLOYEE_EXITED_AREA) == 1
    assert svc._bus.count(EventType.EMPLOYEE_ENTERED_AREA) == 2


# 12) TTL
def test_ttl_current_state(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-02", "Pátio 02")
    service._provider.simulate_location("TRACKER-001", "PATIO-02")
    service.poll_provider("TRACKER-001")

    loc = service.get_tracker_location("TRACKER-001")
    assert loc["state"] == LocationState.CURRENT.value
    assert loc["area_id"] == "PATIO-02"


# 13) expiração
def test_ttl_expires_and_stops_asserting_presence(service, fake_clock):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-02", "Pátio 02")
    service._provider.simulate_location("TRACKER-001", "PATIO-02")
    service.poll_provider("TRACKER-001")

    fake_clock.advance(15)  # entre fresh(10) e ttl(30)
    mid = service.get_tracker_location("TRACKER-001")
    assert mid["state"] == LocationState.LAST_KNOWN.value
    assert mid["area_id"] == "PATIO-02"  # ainda informa, mas como LAST_KNOWN

    fake_clock.advance(20)  # total 35s, além do ttl
    expired = service.get_tracker_location("TRACKER-001")
    assert expired["state"] == LocationState.EXPIRED.value
    assert expired["area_id"] is None  # nunca afirma presença além do TTL


# 14) offline
def test_tracker_goes_offline(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service._provider.simulate_offline("TRACKER-001")

    service.poll_provider("TRACKER-001")

    assert service.get_tracker("TRACKER-001").status == TrackerStatus.OFFLINE
    assert service._bus.count(EventType.TRACKER_OFFLINE) == 1


def test_tracker_offline_event_not_repeated_every_poll(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service._provider.simulate_offline("TRACKER-001")

    service.poll_provider("TRACKER-001")
    service.poll_provider("TRACKER-001")
    service.poll_provider("TRACKER-001")

    assert service._bus.count(EventType.TRACKER_OFFLINE) == 1  # só na transição, não em todo poll


def test_tracker_back_online_returns_to_active(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service._provider.simulate_location("TRACKER-001", "PATIO-01")
    service._provider.simulate_offline("TRACKER-001")
    service.poll_provider("TRACKER-001")
    assert service.get_tracker("TRACKER-001").status == TrackerStatus.OFFLINE

    service._provider.simulate_online("TRACKER-001")
    service.poll_provider("TRACKER-001")

    assert service.get_tracker("TRACKER-001").status == TrackerStatus.ACTIVE


# 15) baixa bateria
def test_tracker_low_battery(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service._provider.simulate_location("TRACKER-001", "PATIO-01")
    service.register_area("PATIO-01", "Pátio 01")
    service._provider.simulate_low_battery("TRACKER-001", 0.05)

    service.poll_provider("TRACKER-001")

    assert service.get_tracker("TRACKER-001").status == TrackerStatus.LOW_BATTERY
    assert service._bus.count(EventType.TRACKER_LOW_BATTERY) == 1


# 16) tracker desconhecido
def test_unknown_tracker_from_service_raises(service):
    with pytest.raises(TrackerNotFoundError):
        service.poll_provider("TRACKER-NUNCA-CADASTRADO")


def test_registered_tracker_unknown_to_provider_returns_unknown_status(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    # Registrado no serviço, mas o provider (mock) nunca recebeu uma
    # simulação de localização para ele — provider.read_location -> None.
    obs = service.poll_provider("TRACKER-001")
    assert obs.status == ObservationStatus.UNKNOWN


# 17) histórico
def test_tracker_history_accumulates(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-01", "Pátio 01")
    service.register_area("PATIO-02", "Pátio 02")

    service._provider.simulate_location("TRACKER-001", "PATIO-01")
    service.poll_provider("TRACKER-001")
    service._provider.simulate_location("TRACKER-001", "PATIO-02")
    service.poll_provider("TRACKER-001")

    history = service.get_tracker_history("TRACKER-001")
    assert len(history) == 2
    assert history[0]["area_id"] == "PATIO-01"
    assert history[1]["area_id"] == "PATIO-02"


def test_employee_history_accumulates(service):
    service.register_area("PATIO-01", "Pátio 01")
    service.register_checkpoint("PATIO-01", "Entrada", checkpoint_id="CK-1")

    service.record_safety_check("FUNC-000234", "PATIO-01", "CK-1", SafetyCheckStatus.COMPLIANT)
    service.record_safety_check("FUNC-000234", "PATIO-01", "CK-1", SafetyCheckStatus.NON_COMPLIANT,
                                 missing_ppe=["gloves"])

    history = service.get_employee_history("FUNC-000234")
    assert len(history) == 2
    assert history[1]["status"] == "NON_COMPLIANT"
    assert history[1]["missing_ppe"] == ["gloves"]


# 18) Safety Check
def test_safety_check_represents_result_does_not_decide(service):
    """O Safety Check nunca calcula COMPLIANT/NON_COMPLIANT sozinho — só
    guarda o que foi decidido em outro lugar (seção 27)."""
    service.register_area("PATIO-02", "Pátio 02")
    service.register_checkpoint("PATIO-02", "Entrada", checkpoint_id="CK-2")

    check = service.record_safety_check(
        "FUNC-000234", "PATIO-02", "CK-2", SafetyCheckStatus.NON_COMPLIANT,
        camera_id="CAM-ENTRY-02", evaluation_id="EVAL-123",
        detected_ppe=["helmet", "vest", "boots"], missing_ppe=["gloves"],
    )
    assert check.status == SafetyCheckStatus.NON_COMPLIANT
    assert check.evaluation_id == "EVAL-123"
    assert check.missing_ppe == ["gloves"]


# 19) EventBus
def test_event_bus_records_full_history(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-01", "Pátio 01")
    service._provider.simulate_location("TRACKER-001", "PATIO-01")
    service.poll_provider("TRACKER-001")

    history = service._bus.history()
    event_types = {et for et, _ in history}
    assert EventType.TRACKER_DETECTED in event_types
    assert EventType.TRACKER_LOCATION_UPDATED in event_types


# 20) métricas
def test_metrics_track_safety_checks_and_trackers(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-02", "Pátio 02")
    service.register_checkpoint("PATIO-02", "Entrada", checkpoint_id="CK-2")
    service.record_safety_check("FUNC-000234", "PATIO-02", "CK-2", SafetyCheckStatus.COMPLIANT)
    service.record_safety_check("FUNC-000234", "PATIO-02", "CK-2", SafetyCheckStatus.NON_COMPLIANT)

    snap = service._metrics.snapshot()
    assert snap["trackers_total"] == 1
    assert snap["safety_checks_total"] == 2
    assert snap["compliant_checks"] == 1
    assert snap["non_compliant_checks"] == 1


def test_metrics_never_contain_biometric_fields(service):
    """Seção 32/33 — nenhuma métrica deve conter campos biométricos, mesmo
    que alguém tente passar isso via metadata."""
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001",
                              metadata={"embedding": "não deveria vazar pra métrica"})
    snap = service._metrics.snapshot()
    assert "embedding" not in str(snap)


# 21) Mock Provider
def test_mock_provider_simulates_full_lifecycle():
    from app.providers.mock_provider import MockTrackerProvider

    provider = MockTrackerProvider()
    assert provider.read_location("TRACKER-999") is None  # desconhecido

    provider.simulate_location("TRACKER-001", "PATIO-01")
    reading = provider.read_location("TRACKER-001")
    assert reading["area_id"] == "PATIO-01"
    assert reading["offline"] is False

    provider.simulate_offline("TRACKER-001")
    reading2 = provider.read_location("TRACKER-001")
    assert reading2["offline"] is True

    provider.simulate_online("TRACKER-001")
    provider.simulate_low_battery("TRACKER-001", 0.05)
    reading3 = provider.read_location("TRACKER-001")
    assert reading3["battery_level"] == 0.05


# 22) contrato de integração com Fusion
def test_fusion_compatible_observation_contract(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-02", "Pátio 02")
    ppe = service.register_ppe_asset(PPEType.HELMET, tracker_id="TRACKER-001")
    service.assign_ppe_to_employee(ppe.ppe_id, "FUNC-000234")
    service._provider.simulate_location("TRACKER-001", "PATIO-02")
    service.poll_provider("TRACKER-001")

    payload = service.build_fusion_compatible_observation("TRACKER-001")
    assert payload["source"] == "tracker"
    assert payload["ppe_type"] == "helmet"
    assert payload["employee_id_assigned"] == "FUNC-000234"  # nomeado "assigned", nunca "worn"
    assert payload["area_id"] == "PATIO-02"
    assert payload["location_state"] == LocationState.CURRENT.value


# 23) EPI sem funcionário
def test_ppe_asset_without_employee_stays_unassigned(service):
    ppe = service.register_ppe_asset(PPEType.BOOTS)
    assert ppe.employee_id is None
    assert ppe.status == PPEAssetStatus.REGISTERED
    all_assets = service.list_ppe_assets()
    assert ppe in all_assets


# 24) EPI atribuído != EPI comprovadamente utilizado (seção 20/21 — inconsistência)
def test_assigned_ppe_location_mismatch_is_possible_inconsistency_not_violation(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-02", "Pátio 02")
    service.register_area("ARMAZEM", "Armazém")
    ppe = service.register_ppe_asset(PPEType.HELMET, tracker_id="TRACKER-001")
    service.assign_ppe_to_employee(ppe.ppe_id, "FUNC-000234")

    # câmera confirmou o funcionário em PATIO-02, mas o tracker do capacete
    # dele está no armazém
    service._provider.simulate_location("TRACKER-001", "ARMAZEM")
    service.poll_provider("TRACKER-001")

    result = service.check_location_inconsistency("FUNC-000234", "PATIO-02", ppe.ppe_id)
    assert result is not None
    assert result.type.value == "POSSIBLE_INCONSISTENCY"
    assert result.ppe_area_id == "ARMAZEM"
    assert service._bus.count(EventType.POSSIBLE_PPE_LOCATION_INCONSISTENCY) == 1
    # o próprio nome do tipo já deixa claro: NUNCA é chamado de "violation"


def test_no_inconsistency_when_areas_match(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-02", "Pátio 02")
    ppe = service.register_ppe_asset(PPEType.HELMET, tracker_id="TRACKER-001")
    service.assign_ppe_to_employee(ppe.ppe_id, "FUNC-000234")
    service._provider.simulate_location("TRACKER-001", "PATIO-02")
    service.poll_provider("TRACKER-001")

    result = service.check_location_inconsistency("FUNC-000234", "PATIO-02", ppe.ppe_id)
    assert result is None


def test_no_inconsistency_when_ppe_has_no_tracker(service):
    ppe = service.register_ppe_asset(PPEType.HELMET)  # sem tracker
    service.assign_ppe_to_employee(ppe.ppe_id, "FUNC-000234")
    result = service.check_location_inconsistency("FUNC-000234", "PATIO-02", ppe.ppe_id)
    assert result is None


# --------------------------------------------------------------------- #
# Fase 3.8B — agregações para a interface
# --------------------------------------------------------------------- #
def test_list_employees_aggregates_from_ppe_and_checks(service):
    service.register_area("PATIO-02", "Pátio 02")
    service.register_checkpoint("PATIO-02", "Entrada", checkpoint_id="CK-1")
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    helmet = service.register_ppe_asset(PPEType.HELMET, tracker_id="TRACKER-001")
    service.assign_ppe_to_employee(helmet.ppe_id, "FUNC-000234")
    service._provider.simulate_location("TRACKER-001", "PATIO-02")
    service.poll_provider("TRACKER-001")
    service.record_safety_check("FUNC-000234", "PATIO-02", "CK-1", SafetyCheckStatus.COMPLIANT)

    employees = service.list_employees()
    assert len(employees) == 1
    emp = employees[0]
    assert emp["employee_id"] == "FUNC-000234"
    assert emp["current_area_id"] == "PATIO-02"
    assert emp["last_check"]["status"] == "COMPLIANT"
    assert emp["assigned_ppe"][0]["area_id"] == "PATIO-02"


def test_list_events_exposes_event_bus_history(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("PATIO-01", "Pátio 01")
    service._provider.simulate_location("TRACKER-001", "PATIO-01")
    service.poll_provider("TRACKER-001")

    events = service.list_events()
    assert any(e["event"] == "TRACKER_DETECTED" for e in events)


def test_list_inconsistencies_persists_across_calls(service):
    service.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-001")
    service.register_area("MANUTENCAO", "Manutenção")
    ppe = service.register_ppe_asset(PPEType.HELMET, tracker_id="TRACKER-001")
    service.assign_ppe_to_employee(ppe.ppe_id, "FUNC-000234")
    service._provider.simulate_location("TRACKER-001", "ARMAZEM_INEXISTENTE_MAS_TUDO_BEM")
    service.poll_provider("TRACKER-001")

    assert service.list_inconsistencies() == []
    service.check_location_inconsistency("FUNC-000234", "MANUTENCAO", ppe.ppe_id)
    assert len(service.list_inconsistencies()) == 1

"""
Teste end-to-end — seção 37 do pedido.

FUNC-000234 entra em PÁTIO-02 (conforme), sai, entra em MANUTENÇÃO (não
conforme — luvas ausentes), enquanto os trackers dos EPIs mostram
localizações próprias, preservadas como evidência distinta, sem inventar
conclusões sobre uso.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.domain.enums import PPEType, SafetyCheckStatus, TrackerTechnology
from app.infrastructure.clock import FakeClock
from app.infrastructure.event_bus import EventType, InMemoryEventBus
from app.observability.metrics import TrackerMetrics
from app.providers.mock_provider import MockTrackerProvider
from app.service import TrackerService


def test_full_scenario_two_areas_different_rules_and_tracker_locations():
    clock = FakeClock(datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc))
    bus = InMemoryEventBus()
    metrics = TrackerMetrics()
    provider = MockTrackerProvider()
    svc = TrackerService(clock, bus, metrics, provider, fresh_seconds=10, ttl_seconds=30)

    # --- Setup: áreas, checkpoints, trackers, EPIs, atribuição ---
    svc.register_area("PATIO-02", "Pátio de Carga 02")
    svc.register_area("MANUTENCAO", "Área de Manutenção")
    svc.register_area("ARMAZEM", "Armazém")
    svc.register_checkpoint("PATIO-02", "Entrada Pátio 02", checkpoint_id="CHECKPOINT-PATIO-02",
                             camera_id="CAM-ENTRY-02")
    svc.register_checkpoint("MANUTENCAO", "Entrada Manutenção", checkpoint_id="CHECKPOINT-MANUTENCAO",
                             camera_id="CAM-ENTRY-MANUTENCAO")

    svc.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-HELMET")
    svc.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-BOOTS")
    svc.register_tracker(TrackerTechnology.MOCK, tracker_id="TRACKER-GLOVES")

    helmet = svc.register_ppe_asset(PPEType.HELMET, tracker_id="TRACKER-HELMET")
    boots = svc.register_ppe_asset(PPEType.BOOTS, tracker_id="TRACKER-BOOTS")
    gloves = svc.register_ppe_asset(PPEType.GLOVES, tracker_id="TRACKER-GLOVES")
    for asset in (helmet, boots, gloves):
        svc.assign_ppe_to_employee(asset.ppe_id, "FUNC-000234")

    # ================================================================= #
    # 1) FUNC-000234 entra em PÁTIO-02 — câmera confirma capacete/vest/boots
    #    (o Safety Check REPRESENTA uma decisão já tomada em outro lugar —
    #    aqui simulamos essa decisão como já pronta, exatamente como o
    #    Rules Engine faria numa integração real futura).
    # ================================================================= #
    check_1 = svc.record_safety_check(
        "FUNC-000234", "PATIO-02", "CHECKPOINT-PATIO-02", SafetyCheckStatus.COMPLIANT,
        camera_id="CAM-ENTRY-02", evaluation_id="EVAL-001",
        detected_ppe=["helmet", "vest", "boots"],
    )
    assert check_1.status == SafetyCheckStatus.COMPLIANT

    provider.simulate_location("TRACKER-HELMET", "PATIO-02")
    provider.simulate_location("TRACKER-BOOTS", "PATIO-02")
    svc.poll_provider("TRACKER-HELMET")
    svc.poll_provider("TRACKER-BOOTS")

    clock.advance(600)  # 10 minutos depois

    # ================================================================= #
    # 2) FUNC-000234 sai de PÁTIO-02 e entra em MANUTENÇÃO — nova regra,
    #    luvas ausentes -> NON_COMPLIANT.
    # ================================================================= #
    check_2 = svc.record_safety_check(
        "FUNC-000234", "MANUTENCAO", "CHECKPOINT-MANUTENCAO", SafetyCheckStatus.NON_COMPLIANT,
        camera_id="CAM-ENTRY-MANUTENCAO", evaluation_id="EVAL-002",
        detected_ppe=["helmet", "boots", "goggles"], missing_ppe=["gloves"],
    )
    assert check_2.status == SafetyCheckStatus.NON_COMPLIANT
    assert check_2.missing_ppe == ["gloves"]

    # Simultaneamente: tracker do capacete e das botas foram junto pra
    # manutenção, mas a luva ficou no armazém.
    provider.simulate_location("TRACKER-HELMET", "MANUTENCAO")
    provider.simulate_location("TRACKER-BOOTS", "MANUTENCAO")
    provider.simulate_location("TRACKER-GLOVES", "ARMAZEM")
    svc.poll_provider("TRACKER-HELMET")
    svc.poll_provider("TRACKER-BOOTS")
    svc.poll_provider("TRACKER-GLOVES")

    # ================================================================= #
    # 3) Conferências finais
    # ================================================================= #

    # O mesmo funcionário está COMPLIANT numa área e NON_COMPLIANT na outra
    # — o sistema PERMITE isso (seção 12 do pedido), sem forçar consistência
    # artificial entre checkpoints diferentes.
    history = svc.get_employee_history("FUNC-000234")
    assert len(history) == 2
    assert history[0]["status"] == "COMPLIANT"
    assert history[0]["area_id"] == "PATIO-02"
    assert history[1]["status"] == "NON_COMPLIANT"
    assert history[1]["area_id"] == "MANUTENCAO"

    # As localizações dos EPIs são preservadas como evidências DISTINTAS,
    # sem o sistema "decidir" sozinho se a luva estava sendo usada ou não.
    gloves_location = svc.get_tracker_location("TRACKER-GLOVES")
    assert gloves_location["area_id"] == "ARMAZEM"
    helmet_location = svc.get_tracker_location("TRACKER-HELMET")
    assert helmet_location["area_id"] == "MANUTENCAO"

    # A ausência de luvas já foi registrada pela câmera (fonte de uso). O
    # tracker da luva está no ARMAZÉM, mas o funcionário (segundo a câmera)
    # está em MANUTENÇÃO — as áreas NÃO batem, então o sistema preserva
    # isso como POSSIBLE_INCONSISTENCY (seção 20/21): nunca vira violação
    # sozinho, só fica registrado como evidência adicional, complementando
    # (não contradizendo) o que a câmera já tinha detectado.
    gloves_check = svc.check_location_inconsistency("FUNC-000234", "MANUTENCAO", gloves.ppe_id)
    assert gloves_check is not None
    assert gloves_check.type.value == "POSSIBLE_INCONSISTENCY"
    assert gloves_check.ppe_area_id == "ARMAZEM"

    # Agora o caso sem inconsistência: o capacete FOI detectado pela câmera
    # em MANUTENÇÃO, e o tracker dele TAMBÉM está lá — concordância total.
    helmet_check = svc.check_location_inconsistency("FUNC-000234", "MANUTENCAO", helmet.ppe_id)
    assert helmet_check is None

    # Métricas finais
    snap = metrics.snapshot()
    assert snap["safety_checks_total"] == 2
    assert snap["compliant_checks"] == 1
    assert snap["non_compliant_checks"] == 1
    assert snap["trackers_total"] == 3

    # Nenhum incidente foi criado por este módulo — isso NUNCA é
    # responsabilidade do epi_tracker (seção 24 do pedido).
    # (Não há Incident Service neste teste de propósito — é exatamente
    # esse o ponto: o Tracker Service não cria incidentes.)

"""
Testes de integração da Fase 3.7 — pipeline de câmera real, ponta a ponta.

Sobem 5 serviços reais (epi_ppe/Vision + epi_identity + epi_fusion +
epi_rules + epi_incident), todos via subprocess/HTTP — nenhum é importado em
processo (mesmo motivo documentado em `app/runner.py`: os módulos
compartilham o nome de pacote `app`).

`epi_ppe` roda com o provider MOCK (`PPE_DETECTOR_PROVIDER=mock`, já
configurado em `runner.start_service`) — as cenas são dicts determinísticos,
não frames de vídeo reais. Isso é intencional (seção 35 do pedido: testes
automatizados não podem depender de webcam nem de pesos de YOLO).
"""
from __future__ import annotations

import itertools

from app.camera_pipeline import IdentityCache, RealCameraPipeline

_counter = itertools.count(1)


def next_seed() -> str:
    return f"SEED37-{next(_counter):04d}"


def enroll_employee(identity_client, name: str = "Funcionário Câmera") -> dict:
    emp = identity_client.create_employee(registration=next_seed(), name=name)
    identity_client.enroll(employee_id=emp["id"], seed=emp["employee_code"])
    return emp


# Caixa-pessoa de referência e as quatro caixas de EPI, todas geometricamente
# válidas para o associador do Módulo 2 (região corporal + contenção) — ver
# app/association/associator.py::EXPECTED_REGION. Usadas em toda a suíte.
PERSON_BBOX = [100, 50, 300, 500]
PPE_BOXES = {
    "HELMET": [140, 60, 260, 150],
    "SAFETY_VEST": [130, 200, 270, 340],
    "GLOVES": [110, 300, 290, 340],
    "SAFETY_BOOTS": [120, 420, 280, 495],
}


def make_scene(camera_id: str, ppe_present: tuple[str, ...], person_confidence: float = 0.95) -> dict:
    """Monta o dict de cena que o provider mock do epi_ppe consome. `camera_id`
    só é usado pelo chamador (VisionClient.process_frame), não pela cena em
    si — o provider mock não sabe nada sobre câmeras."""
    detections = [{"cls": "PERSON", "confidence": person_confidence, "bbox": PERSON_BBOX}]
    for cls in ppe_present:
        detections.append({"cls": cls, "confidence": 0.9, "bbox": PPE_BOXES[cls]})
    return {"detections": detections}


FULL_PPE = ("HELMET", "SAFETY_VEST", "GLOVES", "SAFETY_BOOTS")


# --------------------------------------------------------------------- #
# Cenário A — conformidade total via câmera
# --------------------------------------------------------------------- #
def test_scenario_a_full_compliance_no_incident(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident):
    emp = enroll_employee(cam_identity)
    camera_id = "CAM-A"

    pipe = RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=1, identity_seed_provider=lambda cam, trk: emp["employee_code"],
    )

    scene = make_scene(camera_id, FULL_PPE)
    results = pipe.process_frame(camera_id, scene)

    assert len(results) == 1
    person = results[0]
    assert person.identity_status == "MATCHED"
    assert person.employee_id == emp["employee_code"]
    assert person.display_identity_label == emp["employee_code"]
    assert person.overall_status == "COMPLIANT"
    assert person.incident_actions == []

    incidents = cam_incident.list(employee_id=emp["employee_code"])
    assert incidents == []


# --------------------------------------------------------------------- #
# Cenário B — EPI ausente detectado pela câmera -> incidente
# --------------------------------------------------------------------- #
def test_scenario_b_missing_helmet_creates_incident(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident):
    emp = enroll_employee(cam_identity)
    camera_id = "CAM-B"
    pipe = RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=1, identity_seed_provider=lambda cam, trk: emp["employee_code"],
    )

    scene = make_scene(camera_id, ("SAFETY_VEST", "GLOVES", "SAFETY_BOOTS"))  # sem capacete
    results = pipe.process_frame(camera_id, scene)

    assert len(results) == 1
    person = results[0]
    assert person.ppe["helmet"]["status"] == "MISSING"
    assert person.overall_status == "NON_COMPLIANT"
    assert len(person.incident_actions) == 1
    assert person.incident_actions[0]["action"] == "CREATED"

    incidents = cam_incident.list(employee_id=emp["employee_code"], status="OPEN")
    assert len(incidents) == 1
    assert incidents[0]["ppe_type"] == "helmet"


# --------------------------------------------------------------------- #
# Cenário C — pessoa não identificada -> nenhum incidente individual
# --------------------------------------------------------------------- #
def test_scenario_c_unmatched_identity_no_individual_incident(
    cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
):
    camera_id = "CAM-C"
    # Sem funcionário cadastrado com essa seed -> Identity retorna UNKNOWN.
    pipe = RealCameraPipeline(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
                               process_every_n_frames=1)

    scene = make_scene(camera_id, ("SAFETY_VEST", "GLOVES", "SAFETY_BOOTS"))  # sem capacete
    results = pipe.process_frame(camera_id, scene)

    assert len(results) == 1
    person = results[0]
    assert person.employee_id is None
    assert person.display_identity_label == "unknown"
    assert person.incident_actions == []


# --------------------------------------------------------------------- #
# Cenário D — câmera não enxerga os pés -> NOT_VISIBLE, não gera incidente
# --------------------------------------------------------------------- #
def test_scenario_d_camera_cannot_see_feet_is_not_visible(
    cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
):
    emp = enroll_employee(cam_identity)
    camera_id = "CAM-D"
    pipe = RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=1, identity_seed_provider=lambda cam, trk: emp["employee_code"],
        camera_visibility={"feet": False},
    )

    scene = make_scene(camera_id, ("HELMET", "SAFETY_VEST", "GLOVES"))  # sem botas (câmera não enquadra os pés)
    results = pipe.process_frame(camera_id, scene)

    assert len(results) == 1
    person = results[0]
    assert "boots" not in person.ppe  # builder omitiu — Fusion decide NOT_VISIBLE
    assert person.overall_status in ("INDETERMINATE", "PARTIAL")
    assert person.incident_actions == []


# --------------------------------------------------------------------- #
# LOW_CONFIDENCE / AMBIGUOUS nunca aparecem como identidade confirmada
# --------------------------------------------------------------------- #
def test_low_confidence_identity_never_shown_as_confirmed(pipeline_with_vision, cam_vision, cam_fusion, cam_rules,
                                                            cam_incident):
    from app.identity_client import IdentityClient
    permissive_identity = IdentityClient(pipeline_with_vision.identity_permissive.api_url)
    try:
        emp = enroll_employee(permissive_identity)
        camera_id = "CAM-LC"
        # Seed diferente da cadastrada -> LOW_CONFIDENCE na instância permissiva
        # (ver docs/contracts.md, "Como LOW_CONFIDENCE é reproduzido nos testes").
        pipe = RealCameraPipeline(
            cam_vision, permissive_identity, cam_fusion, cam_rules, cam_incident,
            process_every_n_frames=1, identity_seed_provider=lambda cam, trk: next_seed(),
        )
        scene = make_scene(camera_id, FULL_PPE)
        results = pipe.process_frame(camera_id, scene)

        assert len(results) == 1
        person = results[0]
        assert person.identity_status == "LOW_CONFIDENCE"
        assert person.display_identity_label == "uncertain"
        assert person.display_identity_label != emp["employee_code"]
    finally:
        permissive_identity.close()


# --------------------------------------------------------------------- #
# Amostragem — nem todo frame aciona a cadeia completa
# --------------------------------------------------------------------- #
def test_process_every_n_frames_skips_frames(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident):
    emp = enroll_employee(cam_identity)
    camera_id = "CAM-SAMPLE"
    pipe = RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=3, identity_seed_provider=lambda cam, trk: emp["employee_code"],
    )
    scene = make_scene(camera_id, FULL_PPE)

    r1 = pipe.process_frame(camera_id, scene)  # frame 1 -> pulado
    r2 = pipe.process_frame(camera_id, scene)  # frame 2 -> pulado
    r3 = pipe.process_frame(camera_id, scene)  # frame 3 -> processado

    assert r1 == []
    assert r2 == []
    assert len(r3) == 1
    assert pipe.metrics.frames_received == 3
    assert pipe.metrics.frames_processed == 1


# --------------------------------------------------------------------- #
# Cache de identidade — não chama /recognition/match de novo dentro do TTL
# --------------------------------------------------------------------- #
def test_identity_cache_avoids_repeated_match_calls(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident):
    emp = enroll_employee(cam_identity)
    camera_id = "CAM-CACHE"

    pipe = RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=1, identity_seed_provider=lambda cam, trk: emp["employee_code"],
        identity_cache=IdentityCache(ttl_seconds=60.0),
    )
    scene = make_scene(camera_id, FULL_PPE)

    # O track_id é atribuído pelo tracker do Módulo 2, não por nós — por
    # isso repetimos a MESMA cena na mesma câmera, o que faz o tracker
    # (IoU) reconhecer a mesma pessoa e reutilizar o mesmo track_id.
    r1 = pipe.process_frame(camera_id, scene)
    r2 = pipe.process_frame(camera_id, scene)

    assert r1[0].person_track_id == r2[0].person_track_id  # confirma que é o mesmo track
    assert pipe.metrics.identity_requests == 1
    assert pipe.metrics.identity_cache_hits == 1
    assert r2[0].identity_from_cache is True
    assert r1[0].identity_from_cache is False


# --------------------------------------------------------------------- #
# Frames repetidos (mesma violação observada de novo) não criam um SEGUNDO
# incidente — cada frame vira um evaluation_id novo (não é o teste de
# idempotência por evaluation_id repetido, esse já existe na Fase 3.5), mas
# o Incident Service ainda assim reconhece que é a mesma violação aberta e
# só incrementa occurrence_count (ação UPDATED), nunca cria um incident_id novo.
# --------------------------------------------------------------------- #
def test_repeated_frames_do_not_duplicate_incident(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident):
    emp = enroll_employee(cam_identity)
    camera_id = "CAM-IDEMP"
    pipe = RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=1, identity_seed_provider=lambda cam, trk: emp["employee_code"],
    )
    scene = make_scene(camera_id, ("SAFETY_VEST", "GLOVES", "SAFETY_BOOTS"))  # sem capacete

    r1 = pipe.process_frame(camera_id, scene)
    r2 = pipe.process_frame(camera_id, scene)
    r3 = pipe.process_frame(camera_id, scene)

    # Cada frame gera uma avaliação NOVA (o Rules Engine cria um
    # evaluation_id novo a cada chamada, já que a câmera não reenvia o
    # mesmo evento de propósito como no teste de idempotência da Fase 3.5)
    # — por isso a ação correta para r2/r3 é UPDATED (occurrence_count sobe
    # na violação já aberta), não NOOP (que é reservado para reprocessar
    # exatamente o MESMO evaluation_id). O que realmente importa — e é o
    # que este teste verifica — é que continua sendo UM único incidente.
    assert r1[0].incident_actions[0]["action"] == "CREATED"
    assert r2[0].incident_actions[0]["action"] == "UPDATED"
    assert r3[0].incident_actions[0]["action"] == "UPDATED"

    incident_id = r1[0].incident_actions[0]["incident_id"]
    assert r2[0].incident_actions[0]["incident_id"] == incident_id
    assert r3[0].incident_actions[0]["incident_id"] == incident_id

    open_incidents = cam_incident.list(employee_id=emp["employee_code"], status="OPEN")
    assert len(open_incidents) == 1
    assert open_incidents[0]["occurrence_count"] == 3


# --------------------------------------------------------------------- #
# Múltiplas pessoas no mesmo frame — tratadas de forma independente
# --------------------------------------------------------------------- #
def test_multiple_people_same_frame_independent(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident):
    camera_id = "CAM-MULTI"

    pipe = RealCameraPipeline(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
                               process_every_n_frames=1)

    # Duas pessoas lado a lado no mesmo frame, sem overlap de bounding box.
    person_a_bbox = [50, 50, 200, 480]
    person_b_bbox = [250, 50, 400, 480]
    scene = {
        "detections": [
            {"cls": "PERSON", "confidence": 0.95, "bbox": person_a_bbox},
            {"cls": "PERSON", "confidence": 0.95, "bbox": person_b_bbox},
            {"cls": "HELMET", "confidence": 0.9, "bbox": [90, 60, 170, 150]},   # pessoa A: capacete OK
            {"cls": "HELMET", "confidence": 0.9, "bbox": [290, 60, 370, 150]},  # pessoa B: capacete OK
            # vest/gloves/boots ausentes para as duas, propositalmente.
        ],
    }
    results = pipe.process_frame(camera_id, scene)
    assert len(results) == 2

    # Identidade não foi resolvida (ninguém cadastrado) — validamos que cada
    # pessoa tem seu próprio conjunto de EPIs e nenhuma "vaza" EPI da outra.
    for person in results:
        assert person.ppe["helmet"]["status"] == "DETECTED"
        assert person.ppe["vest"]["status"] == "MISSING"
    assert results[0].person_track_id != results[1].person_track_id


# --------------------------------------------------------------------- #
# Resiliência a erro — Fusion indisponível não derruba o frame nem o loop
# --------------------------------------------------------------------- #
def test_fusion_unavailable_does_not_crash_pipeline(cam_vision, cam_identity, cam_rules, cam_incident):
    from app.clients import FusionClient
    emp_seed = next_seed()
    broken_fusion = FusionClient("http://127.0.0.1:1/api/v1")  # porta inexistente/sem serviço
    try:
        pipe = RealCameraPipeline(
            cam_vision, cam_identity, broken_fusion, cam_rules, cam_incident,
            process_every_n_frames=1, identity_seed_provider=lambda cam, trk: emp_seed,
        )
        scene = make_scene("CAM-ERR", FULL_PPE)

        results = pipe.process_frame("CAM-ERR", scene)  # não deve levantar exceção

        assert len(results) == 1
        assert results[0].overall_status is None  # não conseguiu avaliar, mas não travou
        assert pipe.status.snapshot()["fusion"] == "ERROR"
        assert pipe.metrics.errors_by_service.get("fusion", 0) >= 1
    finally:
        broken_fusion.close()


# --------------------------------------------------------------------- #
# Métricas da camada de pipeline
# --------------------------------------------------------------------- #
def test_pipeline_metrics_snapshot_fields(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident):
    emp = enroll_employee(cam_identity)
    pipe = RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=1, identity_seed_provider=lambda cam, trk: emp["employee_code"],
    )
    scene = make_scene("CAM-METRICS", ("SAFETY_VEST", "GLOVES", "SAFETY_BOOTS"))
    pipe.process_frame("CAM-METRICS", scene)

    snap = pipe.metrics.snapshot()
    assert snap["frames_received"] == 1
    assert snap["frames_processed"] == 1
    assert snap["detections_total"] == 1
    assert snap["observations_generated"] == 1
    assert snap["identity_requests"] == 1
    assert snap["identity_matches"] == 1
    assert snap["fusion_updates"] == 1
    assert snap["rules_evaluations"] == 1
    assert snap["incidents_created"] == 1
    assert snap["pipeline_latency_ms_avg"] >= 0.0

    status = pipe.status.snapshot()
    assert status["vision"] == "ONLINE"
    assert status["identity"] == "ONLINE"
    assert status["fusion"] == "ONLINE"
    assert status["rules"] == "ONLINE"
    assert status["incident"] == "ONLINE"


# --------------------------------------------------------------------- #
# track_id e employee_id continuam sendo conceitos distintos
# --------------------------------------------------------------------- #
def test_track_id_and_employee_id_stay_distinct(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident):
    emp = enroll_employee(cam_identity)
    pipe = RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=1, identity_seed_provider=lambda cam, trk: emp["employee_code"],
    )
    scene = make_scene("CAM-IDS", FULL_PPE)
    results = pipe.process_frame("CAM-IDS", scene)

    person = results[0]
    assert person.person_track_id.startswith("TRACK-")
    assert person.employee_id == emp["employee_code"]
    assert person.person_track_id != person.employee_id


# --------------------------------------------------------------------- #
# Luvas: mão visível e sem luva = violação; mão não enquadrada = nunca violação
# --------------------------------------------------------------------- #
def _glove_pipe(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident, emp, visibility):
    return RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=1, identity_seed_provider=lambda cam, trk: emp["employee_code"],
        camera_visibility=visibility,
    )


def test_gloves_absent_with_hands_visible_is_missing(
    cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
):
    emp = enroll_employee(cam_identity)
    pipe = _glove_pipe(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident, emp, {})
    scene = make_scene("CAM-GLV-1", ("HELMET", "SAFETY_VEST", "SAFETY_BOOTS"))  # sem luvas, mãos visíveis
    person = pipe.process_frame("CAM-GLV-1", scene)[0]
    assert person.ppe["gloves"]["status"] == "MISSING"
    assert person.overall_status == "NON_COMPLIANT"


def test_gloves_not_framed_is_never_a_violation(
    cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
):
    emp = enroll_employee(cam_identity)
    pipe = _glove_pipe(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident, emp, {"hands": False})
    scene = make_scene("CAM-GLV-2", ("HELMET", "SAFETY_VEST", "SAFETY_BOOTS"))  # sem luvas, mas câmera não vê as mãos
    person = pipe.process_frame("CAM-GLV-2", scene)[0]
    assert "gloves" not in person.ppe                      # omitido: Fusion decide NOT_VISIBLE
    assert person.overall_status in ("INDETERMINATE", "PARTIAL")
    assert person.incident_actions == []


# --------------------------------------------------------------------- #
# Evidência escura: a nova tentativa acontece nos quadros seguintes (UPDATED), e só enquanto estiver pendente.
# --------------------------------------------------------------------- #
def test_evidence_retry_runs_on_updated_frames_only_while_pending(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident):
    emp = enroll_employee(cam_identity)
    camera_id = "CAM-EVID-RETRY"
    pipe = RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=1, identity_seed_provider=lambda cam, trk: emp["employee_code"], send_evidence=True,
    )
    calls = []

    def fake_attach(incident_id, frame, person_result, ppe_payload, visibility=None):
        calls.append(incident_id)
        if len(calls) < 3:
            pipe._evidence_pending[incident_id] = len(calls)       # ainda escuro: segue pendente
        else:
            pipe._evidence_pending.pop(incident_id, None)          # achou um quadro bom: encerra

    pipe._attach_evidence = fake_attach
    scene = make_scene(camera_id, ("SAFETY_VEST", "GLOVES", "SAFETY_BOOTS"))     # sem capacete
    actions = [pipe.process_frame(camera_id, scene)[0].incident_actions[0]["action"] for _ in range(6)]
    assert actions[0] == "CREATED" and set(actions[1:]) == {"UPDATED"}
    assert len(calls) == 3 and len(set(calls)) == 1      # criação + 2 tentativas; depois para (não insiste a cada quadro)

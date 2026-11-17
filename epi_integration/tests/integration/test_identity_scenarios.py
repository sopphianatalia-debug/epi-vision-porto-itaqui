"""
Testes de integração da Fase 3.6 — Identity-to-Fusion Integration.

Cobre os cenários 10 a 22 do pedido original (MATCHED, UNMATCHED,
LOW_CONFIDENCE, AMBIGUOUS, propagação de employee_id, pipeline completo,
NOT_VISIBLE, multi-câmera, identidades diferentes, idempotência). Os testes
de erro/observabilidade ficam em test_identity_errors.py.
"""
from __future__ import annotations

import itertools

from app.bridge import (
    build_rules_evaluate_payload,
    enrich_violations_with_cameras,
    identify_and_ingest,
    identity_result_to_fusion_identity,
)

_counter = itertools.count(1)


def next_seed() -> str:
    """Cada seed vira, de forma determinística, um employee_code diferente
    depois de cadastrado — usamos um contador só para não colidir entre
    testes na mesma sessão (o provider mock é 100% determinístico por seed)."""
    return f"SEED-{next(_counter):04d}"


def enroll_employee(identity_client, name: str = "Funcionário Teste") -> dict:
    """Cria e cadastra biometria para um funcionário novo, usando o
    employee_code gerado como seed (mesma convenção dos testes originais do
    epi_identity — ver tests/test_api.py::_create_employee)."""
    emp = identity_client.create_employee(registration=next_seed(), name=name)
    code = emp["employee_code"]
    identity_client.enroll(employee_id=emp["id"], seed=code)
    return emp


FULL_PPE_OK = {
    "helmet": {"status": "DETECTED", "confidence": 0.96},
    "vest": {"status": "DETECTED", "confidence": 0.93},
    "gloves": {"status": "DETECTED", "confidence": 0.94},
    "boots": {"status": "DETECTED", "confidence": 0.91},
}


# --------------------------------------------------------------------- #
# 10 — MATCHED
# --------------------------------------------------------------------- #
def test_matched_propagates_employee_id_to_fusion(identity, fusion):
    emp = enroll_employee(identity)
    code = emp["employee_code"]

    result = identify_and_ingest(
        identity, fusion, camera_id="CAM-01", person_track_id="TRK-01",
        seed=code, ppe=FULL_PPE_OK,
    )
    assert result["match_response"]["status"] == "MATCHED"
    assert result["identity_fields"]["employee_id"] == code
    assert result["identity_fields"]["identity_status"] == "MATCHED"
    assert result["ingest_result"]["employee_id"] == code
    assert result["ingest_result"]["kind"] == "employee_state"

    state = fusion.get_employee_state(code)
    assert state["employee_id"] == code
    assert state["identity_status"] == "MATCHED"


# --------------------------------------------------------------------- #
# 11 — UNMATCHED (RecognitionStatus.UNKNOWN)
# --------------------------------------------------------------------- #
def test_unmatched_does_not_invent_employee_id(identity, fusion, rules, incident):
    # Ninguém foi cadastrado com essa seed -> galeria não reconhece.
    seed = next_seed()

    result = identify_and_ingest(
        identity, fusion, camera_id="CAM-01", person_track_id="TRK-UNK",
        seed=seed, ppe=FULL_PPE_OK,
    )
    assert result["match_response"]["status"] == "UNKNOWN"
    assert result["identity_fields"]["employee_id"] is None
    assert result["ingest_result"]["employee_id"] is None
    assert result["ingest_result"]["kind"] == "anonymous"

    evaluation = rules.evaluate(employee_id=None, ppe=FULL_PPE_OK, identity_status="UNKNOWN")
    assert evaluation["overall_status"] == "NOT_EVALUATED"
    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, None))
    assert results == []


# --------------------------------------------------------------------- #
# 12 — LOW_CONFIDENCE
# --------------------------------------------------------------------- #
def test_low_confidence_does_not_auto_assign(identity_permissive, fusion):
    """Usa a instância permissiva (EPI_SIMILARITY_THRESHOLD=-1.0): com um
    único candidato cadastrado e uma seed de sonda NÃO relacionada, a
    similaridade fica baixa mas ainda "candidata" (threshold=-1), gerando
    confiança abaixo do padrão (0.80) -> LOW_CONFIDENCE de forma
    determinística. Ver docs/contracts.md para o raciocínio completo."""
    emp = enroll_employee(identity_permissive)
    code = emp["employee_code"]

    match_response = identity_permissive.match(camera_id="CAM-01", seed=next_seed())
    assert match_response["status"] == "LOW_CONFIDENCE"

    identity_fields = identity_result_to_fusion_identity(match_response)
    assert identity_fields["employee_id"] is None  # não atribui automaticamente
    assert identity_fields["identity_status"] == "LOW_CONFIDENCE"

    ingest_result = fusion.ingest(
        camera_id="CAM-01", person_track_id="TRK-LC", employee_id=identity_fields["employee_id"],
        identity_status=identity_fields["identity_status"],
        identity_confidence=identity_fields["identity_confidence"], ppe=FULL_PPE_OK,
    )
    assert ingest_result["kind"] == "anonymous"  # Fusion só junta por MATCHED


# --------------------------------------------------------------------- #
# 13 — AMBIGUOUS
# --------------------------------------------------------------------- #
def test_ambiguous_does_not_choose_arbitrarily(identity, fusion):
    """Dois funcionários cadastrados com a MESMA seed (colisão de biometria,
    caso extremo mas determinístico) -> 1º e 2º colocados empatados em
    similaridade -> AMBIGUOUS, sem escolher nenhum dos dois."""
    shared_seed = next_seed()
    emp_a = identity.create_employee(registration=next_seed(), name="Pessoa A")
    identity.enroll(employee_id=emp_a["id"], seed=shared_seed)
    emp_b = identity.create_employee(registration=next_seed(), name="Pessoa B")
    identity.enroll(employee_id=emp_b["id"], seed=shared_seed)

    match_response = identity.match(camera_id="CAM-01", seed=shared_seed)
    assert match_response["status"] == "AMBIGUOUS"
    assert match_response["employee_id"] is None

    identity_fields = identity_result_to_fusion_identity(match_response)
    assert identity_fields["employee_id"] is None
    assert identity_fields["identity_status"] == "AMBIGUOUS"

    ingest_result = fusion.ingest(
        camera_id="CAM-01", person_track_id="TRK-AMB", employee_id=None,
        identity_status="AMBIGUOUS", identity_confidence=identity_fields["identity_confidence"],
        ppe=FULL_PPE_OK,
    )
    assert ingest_result["kind"] == "anonymous"


# --------------------------------------------------------------------- #
# 15/16 — pipeline completo (compliant / non-compliant) com employee_id
#          vindo de verdade do Identity
# --------------------------------------------------------------------- #
def test_full_pipeline_matched_and_compliant_no_incident(identity, fusion, rules, incident):
    emp = enroll_employee(identity)
    code = emp["employee_code"]

    identify_and_ingest(identity, fusion, camera_id="CAM-01", person_track_id="TRK-01",
                         seed=code, ppe=FULL_PPE_OK)
    state = fusion.get_employee_state(code)
    assert state["employee_id"] == code

    payload = build_rules_evaluate_payload(state)
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    assert evaluation["overall_status"] == "COMPLIANT"
    assert evaluation["employee_id"] == code

    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    assert results == []


def test_full_pipeline_matched_and_missing_ppe_creates_incident_with_correct_employee(
    identity, fusion, rules, incident,
):
    emp = enroll_employee(identity)
    code = emp["employee_code"]
    ppe = dict(FULL_PPE_OK)
    ppe["helmet"] = {"status": "MISSING", "confidence": 0.94}

    identify_and_ingest(identity, fusion, camera_id="CAM-01", person_track_id="TRK-01",
                         seed=code, ppe=ppe)
    state = fusion.get_employee_state(code)

    payload = build_rules_evaluate_payload(state, evaluation_id=f"EVAL-{code}")
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    assert evaluation["overall_status"] == "NON_COMPLIANT"
    assert evaluation["employee_id"] == code  # 14 — propagação ponta a ponta

    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    assert len(results) == 1
    inc = results[0]["incident"]
    assert inc["employee_id"] == code  # 14 — chegou íntegro até o Incident
    assert inc["status"] == "OPEN"


# --------------------------------------------------------------------- #
# 17 — identidade desconhecida + EPI ausente: NÃO cria incidente individual
# --------------------------------------------------------------------- #
def test_unmatched_with_missing_ppe_creates_no_incident(identity, fusion, rules, incident):
    seed = next_seed()
    ppe = dict(FULL_PPE_OK)
    ppe["vest"] = {"status": "MISSING", "confidence": 0.9}

    result = identify_and_ingest(identity, fusion, camera_id="CAM-01", person_track_id=f"TRK-{seed}",
                                  seed=seed, ppe=ppe)
    assert result["ingest_result"]["kind"] == "anonymous"

    evaluation = rules.evaluate(employee_id=None, ppe=ppe, identity_status="UNKNOWN")
    assert evaluation["overall_status"] == "NOT_EVALUATED"
    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, None))
    assert results == []


# --------------------------------------------------------------------- #
# 18 — NOT_VISIBLE via pipeline com identidade real
# --------------------------------------------------------------------- #
def test_not_visible_via_identity_pipeline_is_indeterminate(identity, fusion, rules, incident):
    emp = enroll_employee(identity)
    code = emp["employee_code"]
    camera = "CAM-NOFEET"
    fusion.set_visibility_profile(camera, {"face": True, "head": True, "torso": True,
                                            "hands": True, "feet": False})
    ppe = {k: v for k, v in FULL_PPE_OK.items() if k != "boots"}

    identify_and_ingest(identity, fusion, camera_id=camera, person_track_id="TRK-01",
                         seed=code, ppe=ppe)
    state = fusion.get_employee_state(code)
    assert state["ppe"]["boots"]["status"] == "NOT_VISIBLE"

    payload = build_rules_evaluate_payload(state)
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    boots_eval = next(r for res in evaluation["rule_results"] for r in res["requirements"] if r["ppe_type"] == "boots")
    assert boots_eval["result"] == "INDETERMINATE"

    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    assert results == []


# --------------------------------------------------------------------- #
# 19 — multi-câmera, mesmo employee_id (identificado em cada câmera)
# --------------------------------------------------------------------- #
def test_multi_camera_same_employee_consolidates_one_state(identity, fusion):
    emp = enroll_employee(identity)
    code = emp["employee_code"]

    identify_and_ingest(identity, fusion, camera_id="CAM-01", person_track_id="TRK-01",
                         seed=code, ppe={"helmet": FULL_PPE_OK["helmet"]})
    identify_and_ingest(identity, fusion, camera_id="CAM-02", person_track_id="TRK-02",
                         seed=code, ppe={"boots": FULL_PPE_OK["boots"]})

    state = fusion.get_employee_state(code)
    assert state["employee_id"] == code
    assert state["ppe"]["helmet"]["status"] == "DETECTED"
    assert state["ppe"]["boots"]["status"] == "DETECTED"
    assert set(state["observations"].keys()) == {"CAM-01", "CAM-02"}


# --------------------------------------------------------------------- #
# 20 — identidades diferentes entre câmeras não são unificadas
# --------------------------------------------------------------------- #
def test_different_employees_between_cameras_not_merged(identity, fusion):
    emp_a = enroll_employee(identity, name="Pessoa A")
    emp_b = enroll_employee(identity, name="Pessoa B")

    identify_and_ingest(identity, fusion, camera_id="CAM-01", person_track_id="TRK-A",
                         seed=emp_a["employee_code"], ppe=FULL_PPE_OK)
    identify_and_ingest(identity, fusion, camera_id="CAM-02", person_track_id="TRK-B",
                         seed=emp_b["employee_code"], ppe=FULL_PPE_OK)

    state_a = fusion.get_employee_state(emp_a["employee_code"])
    state_b = fusion.get_employee_state(emp_b["employee_code"])
    assert state_a["employee_id"] == emp_a["employee_code"]
    assert state_b["employee_id"] == emp_b["employee_code"]
    assert set(state_a["observations"].keys()) == {"CAM-01"}
    assert set(state_b["observations"].keys()) == {"CAM-02"}


# --------------------------------------------------------------------- #
# 22 — idempotência: reenviar a mesma identificação não duplica nada
# --------------------------------------------------------------------- #
def test_repeated_match_does_not_duplicate_incident(identity, fusion, rules, incident):
    emp = enroll_employee(identity)
    code = emp["employee_code"]
    ppe = dict(FULL_PPE_OK)
    ppe["gloves"] = {"status": "MISSING", "confidence": 0.9}

    # Duas chamadas de identificação "físicas" independentes (a mesma pessoa
    # sendo re-identificada no frame seguinte) alimentando a MESMA avaliação
    # (evaluation_id fixo) — o que deve permanecer idempotente é a camada de
    # Rules/Incident (já provado na Fase 3.5); aqui garantimos que rodar o
    # match do Identity duas vezes não cria dois funcionários nem dois
    # incidentes.
    identify_and_ingest(identity, fusion, camera_id="CAM-01", person_track_id="TRK-01", seed=code, ppe=ppe)
    identify_and_ingest(identity, fusion, camera_id="CAM-01", person_track_id="TRK-01", seed=code, ppe=ppe)

    state = fusion.get_employee_state(code)
    payload = build_rules_evaluate_payload(state, evaluation_id=f"EVAL-{code}-DUP")
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])

    results_1 = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    results_2 = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    assert results_1[0]["action"] == "CREATED"
    assert results_2[0]["action"] == "NOOP"
    assert results_1[0]["incident"]["incident_id"] == results_2[0]["incident"]["incident_id"]

    open_incidents = incident.list(employee_id=code, status="OPEN")
    assert len(open_incidents) == 1

    employees = [e for e in identity.list_employees() if e["employee_code"] == code]
    assert len(employees) == 1  # o match repetido não recriou o funcionário

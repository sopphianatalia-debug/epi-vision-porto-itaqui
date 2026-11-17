"""
Camada de ponte (bridge) — o "cimento" entre os três contratos existentes.

Não reimplementa NENHUMA regra de negócio. Cada função aqui apenas remonta um
payload de um formato de saída de um serviço para o formato de entrada do
próximo, usando exclusivamente campos que os serviços já expõem.

Os dois pontos de fricção genuínos entre os contratos (documentados também em
docs/contracts.md) são:

1. FusionService entrega EmployeeSafetyState.ppe[ppe_type].status como um
   PPEStatus (DETECTED/MISSING/NOT_VISIBLE/NOT_OBSERVED/UNKNOWN/PROPER/
   IMPROPER/PRESENT), MAS quando há conflito não resolvido entre câmeras o
   status vem como UNKNOWN com um campo extra `conflict: true` — o Rules
   Engine tem um ObservedStatus.CONFLICTING dedicado com política própria
   (`conflicting_policy`), então a ponte traduz UNKNOWN+conflict=True para
   "CONFLICTING" antes de mandar ao Rules Engine. Sem essa tradução, um
   conflito de câmeras cairia silenciosamente na política de UNKNOWN em vez
   da política de CONFLICTING.

2. RulesEngine entrega Violation.to_dict() SEM `source_cameras` (o Rules
   Engine não tem conhecimento de câmeras — só recebe o estado já
   consolidado). O IncidentService, por sua vez, guarda source_cameras por
   incidente. A ponte busca, para cada violação, as câmeras contribuintes do
   respectivo EPI no EmployeeSafetyState do Fusion e as anexa antes de
   chamar o Incident Service.
"""
from __future__ import annotations

from typing import Optional


def identity_result_to_fusion_identity(match_response: dict) -> dict:
    """Adapta a saída de POST /recognition/match (epi_identity) para os
    campos de identidade que POST /fusion/observations (epi_fusion) espera.

    Ponto de fricção 3 — os 5 estados de `RecognitionStatus` do Identity não
    mapeiam 1:1 para os 5 estados de `IdentityStatus` do Fusion:

        RecognitionStatus (Identity)  ->  IdentityStatus (Fusion)
        MATCHED                       ->  MATCHED
        LOW_CONFIDENCE                ->  LOW_CONFIDENCE
        AMBIGUOUS                     ->  AMBIGUOUS
        UNKNOWN                       ->  UNKNOWN
        UNAVAILABLE (sem rosto/       ->  NOT_IDENTIFIED
          qualidade insuficiente)

    UNAVAILABLE não tem equivalente no Fusion porque o Fusion nunca soube da
    existência de um "rosto de baixa qualidade" — para ele, não houve
    identificação alguma, o que é exatamente o que NOT_IDENTIFIED significa
    no contrato do Fusion. Em todos os casos que não MATCHED, o Fusion
    (JOINABLE_IDENTITY = {MATCHED}) já trata a observação como não-atribuível
    a um employee_id por conta própria — a tradução aqui só evita passar um
    valor de enum que o Fusion não reconheceria.
    """
    status_map = {
        "MATCHED": "MATCHED",
        "LOW_CONFIDENCE": "LOW_CONFIDENCE",
        "AMBIGUOUS": "AMBIGUOUS",
        "UNKNOWN": "UNKNOWN",
        "UNAVAILABLE": "NOT_IDENTIFIED",
    }
    identity_status = status_map.get(match_response["status"], "UNKNOWN")
    return {
        "employee_id": match_response.get("employee_id") if identity_status == "MATCHED" else None,
        "identity_status": identity_status,
        "identity_confidence": match_response.get("confidence") or 0.0,
    }


def fusion_ppe_to_rules_ppe(fusion_state: dict) -> dict[str, dict]:
    """Converte o `ppe` de um EmployeeSafetyState.to_dict() do Fusion para o
    formato esperado por POST /rules/evaluate."""
    out: dict[str, dict] = {}
    for ppe_type, consolidated in fusion_state.get("ppe", {}).items():
        status = consolidated["status"]
        if consolidated.get("conflict") and status == "UNKNOWN":
            status = "CONFLICTING"
        out[ppe_type] = {"status": status, "confidence": consolidated["confidence"]}
    return out


def build_rules_evaluate_payload(
    fusion_state: dict,
    area: Optional[str] = "PATIO_CARGA",
    operation: Optional[str] = "MOVIMENTACAO_CARGA",
    role: Optional[str] = "OPERADOR",
    evaluation_id: Optional[str] = None,
) -> dict:
    return {
        "employee_id": fusion_state.get("employee_id"),
        "identity_status": fusion_state.get("identity_status", "MATCHED"),
        "area": area,
        "operation": operation,
        "role": role,
        "evaluation_id": evaluation_id,
        "ppe": fusion_ppe_to_rules_ppe(fusion_state),
    }


def enrich_violations_with_cameras(rules_evaluation: dict, fusion_state: Optional[dict]) -> dict:
    """Anexa source_cameras a cada violação, lidas do EmployeeSafetyState do
    Fusion (ConsolidatedPPE.contributing_cameras, exposto como "cameras" em
    to_dict()). Retorna uma cópia — não modifica o dict recebido."""
    if not fusion_state:
        return rules_evaluation
    ppe_cameras = {
        ppe_type: data.get("cameras", [])
        for ppe_type, data in fusion_state.get("ppe", {}).items()
    }
    enriched = dict(rules_evaluation)
    enriched["violations"] = [
        {**v, "source_cameras": ppe_cameras.get(v["ppe_type"], [])}
        for v in rules_evaluation.get("violations", [])
    ]
    return enriched


def identify_and_ingest(
    identity_client,
    fusion_client,
    *,
    camera_id: str,
    person_track_id: str,
    seed: str,
    ppe: dict[str, dict],
    quality: float = 0.95,
) -> dict:
    """Passo Observation -> Identity -> Fusion completo para UMA câmera.

    `seed` é o valor mock que decide quem o provider "reconhece" — ver
    identity_client._frame. Não confundir com employee_id: o employee_id só
    existe DEPOIS que o Identity responde MATCHED; é assim de propósito
    (ver docs/contracts.md, Fase 3.6)."""
    match_response = identity_client.match(camera_id=camera_id, seed=seed, person_track_id=person_track_id,
                                            quality=quality)
    identity_fields = identity_result_to_fusion_identity(match_response)
    ingest_result = fusion_client.ingest(
        camera_id=camera_id, person_track_id=person_track_id, ppe=ppe,
        employee_id=identity_fields["employee_id"],
        identity_status=identity_fields["identity_status"],
        identity_confidence=identity_fields["identity_confidence"],
    )
    return {"match_response": match_response, "identity_fields": identity_fields, "ingest_result": ingest_result}


def evaluate_and_process(
    rules_client,
    incident_client,
    fusion_state: Optional[dict],
    *,
    employee_id: Optional[str],
    identity_status: str = "MATCHED",
    area: Optional[str] = "PATIO_CARGA",
    operation: Optional[str] = "MOVIMENTACAO_CARGA",
    role: Optional[str] = "OPERADOR",
    evaluation_id: Optional[str] = None,
) -> dict:
    """Passo Fusion(state já obtido) -> Rules -> Incident, sem reingerir
    observações. Útil quando várias câmeras já alimentaram o Fusion e só
    queremos disparar uma avaliação sobre o estado atual (cenários
    multi-câmera, idempotência, recuperação)."""
    if fusion_state is not None:
        payload = build_rules_evaluate_payload(
            fusion_state, area=area, operation=operation, role=role, evaluation_id=evaluation_id,
        )
    else:
        payload = {
            "employee_id": employee_id, "identity_status": identity_status,
            "area": area, "operation": operation, "role": role,
            "evaluation_id": evaluation_id, "ppe": {},
        }
    rules_evaluation = rules_client.evaluate(
        employee_id=payload["employee_id"], ppe=payload["ppe"], area=payload["area"],
        operation=payload["operation"], role=payload["role"],
        identity_status=payload["identity_status"], evaluation_id=payload["evaluation_id"],
    )
    enriched = enrich_violations_with_cameras(rules_evaluation, fusion_state)
    incident_results = incident_client.process_evaluation(enriched)
    return {"rules_evaluation": rules_evaluation, "incident_results": incident_results}


def identify_ingest_and_evaluate(
    identity_client,
    fusion_client,
    rules_client,
    incident_client,
    *,
    camera_id: str,
    person_track_id: str,
    seed: str,
    ppe: dict[str, dict],
    quality: float = 0.95,
    area: Optional[str] = "PATIO_CARGA",
    operation: Optional[str] = "MOVIMENTACAO_CARGA",
    role: Optional[str] = "OPERADOR",
    evaluation_id: Optional[str] = None,
) -> dict:
    """Passagem completa de UMA observação pelas 4 etapas: Identity -> Fusion
    -> Rules -> Incident. É a composição de `identify_and_ingest` +
    `evaluate_and_process` já existentes — não duplica nenhuma das duas,
    só encadeia. Introduzida na Fase 3.7 porque o pipeline de câmera real
    precisa dessa passagem completa por pessoa por frame (as fases 3.5/3.6
    só precisavam de pedaços dela nos testes, chamados manualmente)."""
    identify_result = identify_and_ingest(
        identity_client, fusion_client, camera_id=camera_id, person_track_id=person_track_id,
        seed=seed, ppe=ppe, quality=quality,
    )
    employee_id = identify_result["identity_fields"]["employee_id"]
    identity_status = identify_result["identity_fields"]["identity_status"]

    fusion_state = fusion_client.get_employee_state(employee_id) if employee_id else None

    evaluate_result = evaluate_and_process(
        rules_client, incident_client, fusion_state,
        employee_id=employee_id, identity_status=identity_status,
        area=area, operation=operation, role=role, evaluation_id=evaluation_id,
    )

    return {**identify_result, "fusion_state": fusion_state, **evaluate_result}


def run_pipeline(
    fusion_client,
    rules_client,
    incident_client,
    *,
    camera_id: str,
    person_track_id: str,
    ppe: dict[str, dict],
    employee_id: Optional[str],
    area: Optional[str] = "PATIO_CARGA",
    operation: Optional[str] = "MOVIMENTACAO_CARGA",
    role: Optional[str] = "OPERADOR",
    identity_status: str = "MATCHED",
    evaluation_id: Optional[str] = None,
) -> dict:
    """Executa UMA passagem completa do pipeline para uma observação de UMA
    câmera: Observation -> Fusion -> EmployeeSafetyState -> Rules ->
    ComplianceEvaluation -> Incident. Retorna os três resultados intermediários
    para inspeção nos testes."""
    ingest_result = fusion_client.ingest(
        camera_id=camera_id, person_track_id=person_track_id, ppe=ppe,
        employee_id=employee_id, identity_status=identity_status,
    )

    fusion_state = fusion_client.get_employee_state(employee_id) if employee_id else None

    if fusion_state is not None:
        rules_payload = build_rules_evaluate_payload(
            fusion_state, area=area, operation=operation, role=role, evaluation_id=evaluation_id,
        )
    else:
        # Sem employee_id (ou funcionário não identificado): não há estado
        # consolidado no Fusion. Ainda assim avaliamos (o Rules Engine decide
        # NOT_EVALUATED por conta própria — ver EVENTO END-TO-END 9).
        rules_payload = {
            "employee_id": employee_id,
            "identity_status": identity_status,
            "area": area, "operation": operation, "role": role,
            "evaluation_id": evaluation_id, "ppe": {},
        }

    rules_evaluation = rules_client.evaluate(
        employee_id=rules_payload["employee_id"],
        ppe=rules_payload["ppe"],
        area=rules_payload["area"],
        operation=rules_payload["operation"],
        role=rules_payload["role"],
        identity_status=rules_payload["identity_status"],
        evaluation_id=rules_payload["evaluation_id"],
    )

    enriched_evaluation = enrich_violations_with_cameras(rules_evaluation, fusion_state)
    incident_results = incident_client.process_evaluation(enriched_evaluation)

    return {
        "ingest_result": ingest_result,
        "fusion_state": fusion_state,
        "rules_evaluation": rules_evaluation,
        "incident_results": incident_results,
    }

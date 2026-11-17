from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_service
from app.api.schemas import (
    CreateIncidentResponse,
    EvaluationResultItem,
    IncidentOut,
    RulesEvaluationIn,
    ViolationIn,
)
from app.domain.enums import Action
from app.observability.metrics import metrics
from app.service import (
    IncidentAlreadyResolved,
    IncidentNotFound,
    IncidentService,
    InvalidViolation,
)

router = APIRouter()


@router.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@router.post("/incidents", response_model=CreateIncidentResponse, tags=["incidents"])
def create_incident(body: ViolationIn, response: Response, svc: IncidentService = Depends(get_service)):
    """Registra uma violação confirmada. Se já houver incidente ABERTO equivalente,
    não cria outro: deduplica (incrementa occurrence_count) e devolve o existente.
    HTTP 201 quando cria; 200 quando deduplica/atualiza."""
    try:
        incident, action = svc.record_violation(body.to_domain())
    except InvalidViolation as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    response.status_code = status.HTTP_201_CREATED if action == Action.CREATED else status.HTTP_200_OK
    return {**incident.to_dict(svc.now()), "action": action.value}


@router.get("/incidents", response_model=list[IncidentOut], tags=["incidents"])
def list_incidents(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    ppe_type: Optional[str] = None,
    svc: IncidentService = Depends(get_service),
):
    now = svc.now()
    return [i.to_dict(now) for i in svc.list(
        employee_id=employee_id, status=status, severity=severity, ppe_type=ppe_type)]


@router.get("/incidents/{incident_id}", response_model=IncidentOut, tags=["incidents"])
def get_incident(incident_id: str, svc: IncidentService = Depends(get_service)):
    inc = svc.get(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incidente não encontrado.")
    return inc.to_dict(svc.now())


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentOut, tags=["incidents"])
def resolve_incident(incident_id: str, svc: IncidentService = Depends(get_service)):
    try:
        inc = svc.resolve_incident(incident_id)
    except IncidentNotFound:
        raise HTTPException(status_code=404, detail="Incidente não encontrado.")
    except IncidentAlreadyResolved:
        raise HTTPException(status_code=409, detail="Incidente já resolvido.")
    return inc.to_dict(svc.now())


@router.post("/incidents/evaluations", response_model=list[EvaluationResultItem], tags=["incidents"])
def process_evaluation(body: RulesEvaluationIn, svc: IncidentService = Depends(get_service)):
    """FASE 3.5 — integração ponta-a-ponta.

    Único endpoint novo desta fase. Não reimplementa nenhuma regra de negócio:
    apenas expõe via HTTP o método `IncidentService.process_evaluation`, que já
    existia e já era testado (abre/deduplica/idempotência/auto-resolve). Sem
    este endpoint, o comportamento de auto-resolução ao voltar a COMPLIANT e o
    fechamento de EPIs que deixaram de estar em violação não seriam acionáveis
    via API — só POST /incidents (abre 1 violação) e POST /incidents/{id}/resolve
    (resolve por id) existiam, e nenhum dos dois cobre esse fluxo agregado.
    Espera o dict de ComplianceEvaluation do Rules Engine; source_cameras deve
    ser preenchido pela camada de integração a partir do EmployeeSafetyState do
    FusionService antes de enviar (o Rules Engine não carrega essa informação).
    """
    now = svc.now()
    results = svc.process_evaluation(body.to_domain())
    return [{"action": action.value, "incident": inc.to_dict(now)} for inc, action in results]


@router.get("/incidents/metrics/snapshot", tags=["observability"])
def incident_metrics():
    return metrics.snapshot()

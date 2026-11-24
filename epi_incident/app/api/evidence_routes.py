"""Evidência em imagem do incidente. Nunca há URL pública: a imagem só sai com login (Authorization)."""
from __future__ import annotations

import base64
import binascii
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.deps import get_evidence, get_service
from app.auth import current_user, machine_only
from app.evidence import (EvidenceDisabled, EvidenceForbidden, EvidenceGone, EvidenceNotFound,
                          EvidenceService, InvalidEvidence)
from app.service import IncidentService

router = APIRouter(tags=["evidence"])


class EvidenceIn(BaseModel):
    image_base64: str = Field(min_length=8, max_length=2_000_000)
    detections: Optional[list[dict]] = None
    findings: Optional[list[dict]] = None


def _incident(svc: IncidentService, incident_id: str):
    inc = svc.get(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incidente não encontrado.")
    return inc


def _user(user: Optional[dict]) -> dict:
    if user is None:
        raise HTTPException(status_code=503, detail="Evidência exige login ativo (INC_AUTH_MODE=required).")
    return user


def _supervisor(user: Optional[dict]) -> dict:
    user = _user(user)
    if user["role"] != "SUPERVISOR":
        raise HTTPException(status_code=403, detail="Somente supervisor.")
    return user


def _map(exc: Exception) -> HTTPException:
    if isinstance(exc, EvidenceDisabled):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, EvidenceForbidden):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, EvidenceNotFound):
        return HTTPException(status_code=404, detail="Evidência não encontrada.")
    if isinstance(exc, EvidenceGone):
        return HTTPException(status_code=410, detail="Imagem apagada pelo prazo de retenção.")
    return HTTPException(status_code=422, detail=str(exc))


@router.post("/incidents/{incident_id}/evidence", status_code=201, dependencies=[Depends(machine_only)])
def upload(incident_id: str, body: EvidenceIn, svc: IncidentService = Depends(get_service),
           ev: EvidenceService = Depends(get_evidence)):
    """Serviço → Incident: o RECORTE da pessoa (JPEG/PNG, ≤1 MB, ≤1280 px) + caixas normalizadas 0..1."""
    inc = _incident(svc, incident_id)
    try:
        data = base64.b64decode(body.image_base64, validate=True)
        meta = ev.add(inc, data, body.detections, svc.now(), body.findings)
        return meta.public(ev.expires_at(inc, meta))
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="image_base64 inválido.")
    except (EvidenceDisabled, InvalidEvidence) as exc:
        raise _map(exc)


@router.get("/incidents/{incident_id}/evidence")
def list_evidence(incident_id: str, svc: IncidentService = Depends(get_service),
                  ev: EvidenceService = Depends(get_evidence), user: Optional[dict] = Depends(current_user)):
    inc = _incident(svc, incident_id)
    try:
        return ev.list(inc, _user(user))
    except (EvidenceDisabled, EvidenceForbidden) as exc:
        raise _map(exc)


@router.get("/incidents/{incident_id}/evidence/{evidence_id}/image")
def image(incident_id: str, evidence_id: str, svc: IncidentService = Depends(get_service),
          ev: EvidenceService = Depends(get_evidence), user: Optional[dict] = Depends(current_user)):
    inc = _incident(svc, incident_id)
    try:
        data, mime = ev.image(inc, evidence_id, _user(user), svc.now())
    except (EvidenceDisabled, EvidenceForbidden, EvidenceNotFound, EvidenceGone) as exc:
        raise _map(exc)
    return Response(content=data, media_type=mime,
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/incidents/{incident_id}/evidence/{evidence_id}", status_code=204)
def delete(incident_id: str, evidence_id: str, svc: IncidentService = Depends(get_service),
           ev: EvidenceService = Depends(get_evidence), user: Optional[dict] = Depends(current_user)):
    """Supervisor apaga a imagem antes do prazo (ex.: pedido do titular, LGPD)."""
    inc = _incident(svc, incident_id)
    try:
        ev.delete(inc, evidence_id, _supervisor(user), svc.now())
    except (EvidenceDisabled, EvidenceNotFound, EvidenceGone) as exc:
        raise _map(exc)
    return Response(status_code=204)


@router.get("/incidents/{incident_id}/evidence-access-log")
def access_log(incident_id: str, svc: IncidentService = Depends(get_service),
               ev: EvidenceService = Depends(get_evidence), user: Optional[dict] = Depends(current_user)):
    _supervisor(user)
    _incident(svc, incident_id)
    try:
        return ev.access_log(incident_id)
    except EvidenceDisabled as exc:
        raise _map(exc)


@router.post("/evidence/purge")
def purge(svc: IncidentService = Depends(get_service), ev: EvidenceService = Depends(get_evidence),
          user: Optional[dict] = Depends(current_user)):
    _supervisor(user)
    return {"purged": ev.purge_expired(svc.get, svc.now())}

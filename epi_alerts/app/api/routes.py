from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_service, get_sources
from app.service import AlertNotFoundError, AlertService

router = APIRouter()


@router.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@router.get("/alerts", tags=["alerts"])
def list_alerts(status: Optional[str] = None, severity: Optional[str] = None,
                source: Optional[str] = None, include_resolved: bool = False,
                svc: AlertService = Depends(get_service), sources=Depends(get_sources)):
    svc.sync_if_stale(sources)
    return [a.to_dict() for a in svc.list(status, severity, source, include_resolved)]


@router.get("/alerts/summary", tags=["alerts"])
def alerts_summary(svc: AlertService = Depends(get_service), sources=Depends(get_sources)):
    svc.sync_if_stale(sources)
    return svc.summary()


@router.post("/alerts/sync", tags=["alerts"])
def force_sync(svc: AlertService = Depends(get_service), sources=Depends(get_sources)):
    svc.sync(sources)
    return svc.summary()


@router.post("/alerts/{alert_id}/ack", tags=["alerts"])
def acknowledge(alert_id: str, svc: AlertService = Depends(get_service)):
    try:
        return svc.acknowledge(alert_id).to_dict()
    except AlertNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Alerta não encontrado.") from exc

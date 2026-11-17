from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_fusion_service, get_orchestrator, get_ppe_location_service
from app.api.schemas import (
    CameraHealthList,
    IngestOut,
    ObservationIn,
    VisibilityProfileIn,
    VisibilityProfileOut,
)
from app.domain.models import CameraVisibilityProfile
from app.fusion import FusionService
from app.observability.metrics import metrics
from app.orchestrator import CameraObservationOrchestrator
from app.ppe_location import PPELocationService

router = APIRouter()


@router.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@router.post("/fusion/observations", response_model=IngestOut, tags=["fusion"])
def ingest(body: ObservationIn, orch: CameraObservationOrchestrator = Depends(get_orchestrator)):
    result = orch.submit(
        camera_id=body.camera_id,
        person_track_id=body.person_track_id,
        identity_status=body.identity_status.value,
        identity_confidence=body.identity_confidence,
        employee_id=body.employee_id,
        ppe={k.value: {"status": v.status.value, "confidence": v.confidence} for k, v in body.ppe.items()},
        timestamp=body.timestamp,
        observation_id=body.observation_id,
    )
    return IngestOut(
        employee_id=result.employee_id,
        identity_status=result.identity_status.value,
        kind=result.kind,
        reason=result.reason,
    )


@router.get("/fusion/employees/{employee_id}", tags=["fusion"])
def employee_state(employee_id: str, svc: FusionService = Depends(get_fusion_service)):
    state = svc.get_employee_state(employee_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Estado não encontrado para este funcionário.")
    return state.to_dict()


@router.get("/fusion/employees/{employee_id}/observations", tags=["fusion"])
def employee_observations(employee_id: str, svc: FusionService = Depends(get_fusion_service)):
    return [
        {
            "observation_id": o.observation_id, "camera_id": o.camera_id,
            "timestamp": o.timestamp.isoformat(), "person_track_id": o.person_track_id,
            "ppe": {p.value: {"status": e.status.value, "confidence": e.confidence} for p, e in o.ppe.items()},
        }
        for o in svc.get_recent_observations(employee_id)
    ]


@router.get("/fusion/cameras/{camera_id}/observations", tags=["fusion"])
def camera_observations(camera_id: str, svc: FusionService = Depends(get_fusion_service)):
    return [
        {"observation_id": o.observation_id, "employee_id": o.employee_id,
         "person_track_id": o.person_track_id, "timestamp": o.timestamp.isoformat()}
        for o in svc.get_camera_state(camera_id)
    ]


@router.get("/fusion/anonymous", tags=["fusion"])
def anonymous(limit: int = 50, svc: FusionService = Depends(get_fusion_service)):
    return [a.to_dict() for a in svc.get_anonymous_observations(limit)]


@router.get("/fusion/conflicts", tags=["fusion"])
def conflicts(limit: int = 50, svc: FusionService = Depends(get_fusion_service)):
    return [c.to_dict() for c in svc.get_conflicts(limit)]


@router.get("/fusion/state", tags=["fusion"])
def all_states(svc: FusionService = Depends(get_fusion_service)):
    return [s.to_dict() for s in svc.get_all_states()]


@router.post("/fusion/cameras/{camera_id}/visibility", response_model=VisibilityProfileOut, tags=["visibility"])
def set_visibility(camera_id: str, body: VisibilityProfileIn, svc: FusionService = Depends(get_fusion_service)):
    profile = CameraVisibilityProfile(camera_id=camera_id, visibility=body.visibility)
    svc.set_visibility_profile(profile)
    return VisibilityProfileOut(camera_id=camera_id, visibility={k.value: v for k, v in body.visibility.items()})


@router.get("/fusion/cameras/{camera_id}/visibility", response_model=VisibilityProfileOut, tags=["visibility"])
def get_visibility(camera_id: str, svc: FusionService = Depends(get_fusion_service)):
    profile = svc.get_visibility_profile(camera_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil de visibilidade não configurado.")
    return VisibilityProfileOut(camera_id=camera_id, visibility={k.value: v for k, v in profile.visibility.items()})


@router.get("/fusion/metrics", tags=["observability"])
def fusion_metrics():
    return metrics.snapshot()


@router.get("/fusion/cameras/health", response_model=CameraHealthList, tags=["observability"])
def cameras_health():
    """Saúde operacional por câmera, ordenada da pior para a melhor.

    health_score é um indicador operacional (não um diagnóstico de defeito físico).
    """
    return CameraHealthList(cameras=metrics.camera_health())


# --------------------------------------------------------------------- #
# Evidência de localização de EPI (tracker) — fonte separada da câmera.
# Não altera a consolidação por câmera nem a conformidade.
# --------------------------------------------------------------------- #
class PPELocationIn(BaseModel):
    source: str = "tracker"
    tracker_id: str
    ppe_id: Optional[str] = None
    ppe_type: Optional[str] = None
    employee_id_assigned: Optional[str] = None
    area_id: Optional[str] = None
    location_state: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    timestamp: Optional[str] = None


class CameraAreaIn(BaseModel):
    area_id: str


@router.post("/fusion/ppe-locations", tags=["ppe-location"])
def ingest_ppe_location(body: PPELocationIn, svc: PPELocationService = Depends(get_ppe_location_service)):
    try:
        ev = svc.ingest(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ev.to_dict()


@router.post("/fusion/cameras/{camera_id}/area", tags=["ppe-location"])
def set_camera_area(camera_id: str, body: CameraAreaIn, svc: PPELocationService = Depends(get_ppe_location_service)):
    svc.set_camera_area(camera_id, body.area_id)
    return {"camera_id": camera_id, "area_id": body.area_id}


@router.get("/fusion/employees/{employee_id}/ppe-locations", tags=["ppe-location"])
def employee_ppe_locations(employee_id: str, svc: PPELocationService = Depends(get_ppe_location_service)):
    return svc.employee_view(employee_id)


@router.get("/fusion/ppe-inconsistencies", tags=["ppe-location"])
def ppe_inconsistencies(svc: PPELocationService = Depends(get_ppe_location_service)):
    return svc.all_inconsistencies()

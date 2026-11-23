from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_metrics, get_provider, get_service
from app.api.schemas import (
    AssignPPEIn,
    CameraIn,
    InconsistencyCheckIn,
    RegisterAreaIn,
    RegisterCheckpointIn,
    RegisterPPEAssetIn,
    RegisterReaderIn,
    RegisterTrackerIn,
    SafetyCheckIn,
    SimulateBatteryIn,
    SimulateLocationIn,
    SimulateOfflineIn,
    UpdateTrackerIn,
)
from app.domain.models import CameraAlreadyRegisteredError, CameraNotFoundError, TrackerAlreadyRegisteredError
from app.service import (
    AreaNotFoundError,
    CheckpointNotFoundError,
    PPEAssetNotFoundError,
    ReaderNotFoundError,
    TrackerNotFoundError,
    TrackerService,
)

router = APIRouter()


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


# --------------------------------------------------------------------- #
# Trackers
# --------------------------------------------------------------------- #
@router.post("/trackers", status_code=201, tags=["trackers"])
def register_tracker(body: RegisterTrackerIn, svc: TrackerService = Depends(get_service)):
    try:
        tracker = svc.register_tracker(body.technology, body.tracker_id, body.metadata)
    except TrackerAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return tracker.to_dict()


@router.get("/trackers", tags=["trackers"])
def list_trackers(svc: TrackerService = Depends(get_service)):
    return [t.to_dict() for t in svc.list_trackers()]


@router.get("/trackers/{tracker_id}", tags=["trackers"])
def get_tracker(tracker_id: str, svc: TrackerService = Depends(get_service)):
    try:
        return svc.get_tracker(tracker_id).to_dict()
    except TrackerNotFoundError as exc:
        raise _not_found(exc) from exc


@router.put("/trackers/{tracker_id}", tags=["trackers"])
def update_tracker(tracker_id: str, body: UpdateTrackerIn, svc: TrackerService = Depends(get_service)):
    try:
        return svc.update_tracker(tracker_id, body.status, body.metadata).to_dict()
    except TrackerNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/trackers/{tracker_id}/location", tags=["trackers"])
def get_tracker_location(tracker_id: str, svc: TrackerService = Depends(get_service)):
    try:
        return svc.get_tracker_location(tracker_id)
    except TrackerNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/trackers/{tracker_id}/history", tags=["trackers"])
def get_tracker_history(tracker_id: str, svc: TrackerService = Depends(get_service)):
    try:
        return svc.get_tracker_history(tracker_id)
    except TrackerNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/trackers/{tracker_id}/poll", tags=["trackers"])
def poll_tracker(tracker_id: str, svc: TrackerService = Depends(get_service)):
    """Força uma leitura do provider agora (fora do fluxo de polling
    automático — útil para testes/demonstração)."""
    try:
        return svc.poll_provider(tracker_id).to_dict()
    except TrackerNotFoundError as exc:
        raise _not_found(exc) from exc


# --------------------------------------------------------------------- #
# PPE Assets
# --------------------------------------------------------------------- #
@router.post("/ppe", status_code=201, tags=["ppe"])
def register_ppe(body: RegisterPPEAssetIn, svc: TrackerService = Depends(get_service)):
    try:
        asset = svc.register_ppe_asset(body.ppe_type, body.tracker_id, body.metadata)
    except TrackerNotFoundError as exc:
        raise _not_found(exc) from exc
    return asset.to_dict()


@router.get("/ppe", tags=["ppe"])
def list_ppe(svc: TrackerService = Depends(get_service)):
    return [a.to_dict() for a in svc.list_ppe_assets()]


@router.get("/ppe/{ppe_id}", tags=["ppe"])
def get_ppe(ppe_id: str, svc: TrackerService = Depends(get_service)):
    try:
        return svc.get_ppe_asset(ppe_id).to_dict()
    except PPEAssetNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/ppe/{ppe_id}/assign", tags=["ppe"])
def assign_ppe(ppe_id: str, body: AssignPPEIn, svc: TrackerService = Depends(get_service)):
    try:
        return svc.assign_ppe_to_employee(ppe_id, body.employee_id).to_dict()
    except PPEAssetNotFoundError as exc:
        raise _not_found(exc) from exc


# --------------------------------------------------------------------- #
# Areas, Readers, Checkpoints
# --------------------------------------------------------------------- #
@router.post("/areas", status_code=201, tags=["areas"])
def register_area(body: RegisterAreaIn, svc: TrackerService = Depends(get_service)):
    return svc.register_area(body.area_id, body.name, body.type, body.description).to_dict()


@router.get("/areas", tags=["areas"])
def list_areas(svc: TrackerService = Depends(get_service)):
    return [a.to_dict() for a in svc.list_areas()]


@router.get("/areas/{area_id}", tags=["areas"])
def get_area(area_id: str, svc: TrackerService = Depends(get_service)):
    try:
        return svc.get_area(area_id).to_dict()
    except AreaNotFoundError as exc:
        raise _not_found(exc) from exc


# --------------------------------------------------------------------- #
# Câmeras (cadastro administrativo)
# --------------------------------------------------------------------- #
@router.post("/cameras", status_code=201, tags=["cameras"])
def register_camera(body: CameraIn, svc: TrackerService = Depends(get_service)):
    if not body.camera_id or not body.camera_id.strip():
        raise HTTPException(status_code=422, detail="camera_id é obrigatório na criação")
    try:
        cam = svc.register_camera(body.camera_id.strip(), body.name, body.sector, body.kind,
                                  body.pos["x"], body.pos["y"], body.active, body.example,
                                  body.latitude, body.longitude)
    except CameraAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return cam.to_dict()


@router.get("/cameras", tags=["cameras"])
def list_cameras(svc: TrackerService = Depends(get_service)):
    return [c.to_dict() for c in svc.list_cameras()]


@router.get("/cameras/{camera_id}", tags=["cameras"])
def get_camera(camera_id: str, svc: TrackerService = Depends(get_service)):
    try:
        return svc.get_camera(camera_id).to_dict()
    except CameraNotFoundError as exc:
        raise _not_found(exc) from exc


@router.put("/cameras/{camera_id}", tags=["cameras"])
def update_camera(camera_id: str, body: CameraIn, svc: TrackerService = Depends(get_service)):
    try:
        cam = svc.update_camera(camera_id, body.name, body.sector, body.kind,
                                body.pos["x"], body.pos["y"], body.active, body.example,
                                  body.latitude, body.longitude)
    except CameraNotFoundError as exc:
        raise _not_found(exc) from exc
    return cam.to_dict()


@router.delete("/cameras/{camera_id}", status_code=204, tags=["cameras"])
def delete_camera(camera_id: str, svc: TrackerService = Depends(get_service)):
    try:
        svc.delete_camera(camera_id)
    except CameraNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/areas/{area_id}/trackers", tags=["areas"])
def get_area_trackers(area_id: str, svc: TrackerService = Depends(get_service)):
    try:
        return svc.get_trackers_in_area(area_id)
    except AreaNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/readers", status_code=201, tags=["readers"])
def register_reader(body: RegisterReaderIn, svc: TrackerService = Depends(get_service)):
    try:
        return svc.register_reader(body.area_id, body.technology, body.reader_id).to_dict()
    except AreaNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/readers", tags=["readers"])
def list_readers(svc: TrackerService = Depends(get_service)):
    return [r.to_dict() for r in svc.list_readers()]


@router.post("/checkpoints", status_code=201, tags=["checkpoints"])
def register_checkpoint(body: RegisterCheckpointIn, svc: TrackerService = Depends(get_service)):
    try:
        return svc.register_checkpoint(body.area_id, body.name, body.checkpoint_id,
                                        body.camera_id, body.reader_id).to_dict()
    except (AreaNotFoundError, ReaderNotFoundError) as exc:
        raise _not_found(exc) from exc


@router.get("/checkpoints", tags=["checkpoints"])
def list_checkpoints(svc: TrackerService = Depends(get_service)):
    return [c.to_dict() for c in svc.list_checkpoints()]


# --------------------------------------------------------------------- #
# Demo / simulação (provider mock — seção 25)
# --------------------------------------------------------------------- #
@router.post("/demo/location", tags=["demo"])
def demo_location(body: SimulateLocationIn, provider=Depends(get_provider)):
    provider.simulate_location(body.tracker_id, body.area_id, body.signal_strength)
    return {"ok": True}


@router.post("/demo/battery", tags=["demo"])
def demo_battery(body: SimulateBatteryIn, provider=Depends(get_provider)):
    provider.simulate_low_battery(body.tracker_id, body.level) if body.level < 1.0 else \
        provider.simulate_battery_ok(body.tracker_id, body.level)
    return {"ok": True}


@router.post("/demo/offline", tags=["demo"])
def demo_offline(body: SimulateOfflineIn, provider=Depends(get_provider)):
    provider.simulate_offline(body.tracker_id)
    return {"ok": True}


@router.post("/demo/online", tags=["demo"])
def demo_online(body: SimulateOfflineIn, provider=Depends(get_provider)):
    provider.simulate_online(body.tracker_id)
    return {"ok": True}


# --------------------------------------------------------------------- #
# Safety Check
# --------------------------------------------------------------------- #
@router.post("/checks", status_code=201, tags=["checks"])
def record_safety_check(body: SafetyCheckIn, svc: TrackerService = Depends(get_service)):
    try:
        check = svc.record_safety_check(
            body.employee_id, body.area_id, body.checkpoint_id, body.status,
            body.camera_id, body.evaluation_id, body.detected_ppe, body.missing_ppe,
        )
    except (AreaNotFoundError, CheckpointNotFoundError) as exc:
        raise _not_found(exc) from exc
    return check.to_dict()


@router.get("/employees/{employee_id}/history", tags=["checks"])
def get_employee_history(employee_id: str, svc: TrackerService = Depends(get_service)):
    return svc.get_employee_history(employee_id)


# --------------------------------------------------------------------- #
# Inconsistência de localização
# --------------------------------------------------------------------- #
@router.post("/inconsistency-check", tags=["checks"])
def check_inconsistency(body: InconsistencyCheckIn, svc: TrackerService = Depends(get_service)):
    try:
        result = svc.check_location_inconsistency(body.employee_id, body.expected_area_id, body.ppe_id)
    except PPEAssetNotFoundError as exc:
        raise _not_found(exc) from exc
    return result.to_dict() if result else {"inconsistency": None}


# --------------------------------------------------------------------- #
# Contrato compatível com Fusion (não chama o Fusion de verdade nesta fase)
# --------------------------------------------------------------------- #
@router.get("/trackers/{tracker_id}/fusion-observation", tags=["fusion-contract"])
def get_fusion_compatible_observation(tracker_id: str, svc: TrackerService = Depends(get_service)):
    try:
        return svc.build_fusion_compatible_observation(tracker_id)
    except TrackerNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/employees", tags=["employees"])
def list_employees(svc: TrackerService = Depends(get_service)):
    return svc.list_employees()


@router.get("/employees/{employee_id}/summary", tags=["employees"])
def get_employee_summary(employee_id: str, svc: TrackerService = Depends(get_service)):
    return svc.get_employee_summary(employee_id)


@router.get("/inconsistencies", tags=["checks"])
def list_inconsistencies(svc: TrackerService = Depends(get_service)):
    return [i.to_dict() for i in svc.list_inconsistencies()]


@router.get("/events", tags=["observability"])
def list_events(limit: int = 100, svc: TrackerService = Depends(get_service)):
    return svc.list_events(limit)


# --------------------------------------------------------------------- #
# Observabilidade
# --------------------------------------------------------------------- #
@router.get("/metrics", tags=["observability"])
def get_metrics_endpoint(metrics_snapshot=Depends(get_metrics)):
    return metrics_snapshot.snapshot()

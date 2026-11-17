from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.fusion import FusionService, build_fusion_service
from app.infrastructure import Clock
from app.orchestrator import CameraObservationOrchestrator
from app.ppe_location import PPELocationService


@lru_cache
def _clock() -> Clock:
    return Clock()


@lru_cache
def get_fusion_service() -> FusionService:
    return build_fusion_service(get_settings(), clock=_clock())


@lru_cache
def get_orchestrator() -> CameraObservationOrchestrator:
    return CameraObservationOrchestrator(get_fusion_service(), _clock())


@lru_cache
def get_ppe_location_service() -> PPELocationService:
    fusion = get_fusion_service()
    return PPELocationService(
        _clock(), fusion.get_employee_state, ttl_seconds=get_settings().state_ttl_seconds
    )

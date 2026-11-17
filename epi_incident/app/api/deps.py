from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.infrastructure import Clock, InMemoryEventBus, IncidentRepository
from app.service import IncidentService


@lru_cache
def get_service() -> IncidentService:
    settings = get_settings()
    repo = IncidentRepository(settings.id_prefix, settings.id_width, settings.max_history)
    return IncidentService(settings, Clock(), InMemoryEventBus(), repo)

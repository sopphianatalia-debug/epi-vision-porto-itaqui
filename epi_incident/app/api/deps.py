from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.infrastructure import Clock, InMemoryEventBus, IncidentRepository, SqliteIncidentRepository
from app.service import IncidentService


@lru_cache
def get_service() -> IncidentService:
    settings = get_settings()
    if settings.db_path:
        repo = SqliteIncidentRepository(settings.db_path, settings.id_prefix, settings.id_width)
    else:
        repo = IncidentRepository(settings.id_prefix, settings.id_width, settings.max_history)
    return IncidentService(settings, Clock(), InMemoryEventBus(), repo)

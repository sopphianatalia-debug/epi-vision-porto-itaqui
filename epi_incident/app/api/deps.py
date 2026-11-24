from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.infrastructure import Clock, InMemoryEventBus, IncidentRepository, SqliteIncidentRepository
from app.evidence import EvidenceService, EvidenceStore
from app.service import IncidentService
from app.workers import WorkerDirectory


@lru_cache
def get_hub():
    from app.api.ws import WsHub
    return WsHub()


@lru_cache
def get_service() -> IncidentService:
    settings = get_settings()
    if settings.db_path:
        repo = SqliteIncidentRepository(settings.db_path, settings.id_prefix, settings.id_width)
    else:
        repo = IncidentRepository(settings.id_prefix, settings.id_width, settings.max_history)
    bus = InMemoryEventBus()
    bus.subscribe(get_hub().on_event)
    return IncidentService(settings, Clock(), bus, repo)


@lru_cache
def get_evidence() -> EvidenceService:
    settings = get_settings()
    store = EvidenceStore(settings.evidence_dir, settings.db_path) if settings.evidence_dir else None
    return EvidenceService(settings, store)


@lru_cache
def get_workers() -> WorkerDirectory:
    settings = get_settings()
    return WorkerDirectory(settings.identity_url, settings.jwt_secret)

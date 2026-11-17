from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.infrastructure.clock import Clock
from app.infrastructure.event_bus import InMemoryEventBus
from app.providers.mock_provider import MockTrackerProvider
from app.service import TrackerService


@lru_cache
def get_metrics():
    from app.observability.metrics import TrackerMetrics
    return TrackerMetrics()


@lru_cache
def get_provider() -> MockTrackerProvider:
    return MockTrackerProvider()


@lru_cache
def get_service() -> TrackerService:
    settings = get_settings()
    return TrackerService(
        clock=Clock(), event_bus=InMemoryEventBus(), metrics=get_metrics(), location_provider=get_provider(),
        fresh_seconds=settings.location_fresh_seconds, ttl_seconds=settings.location_ttl_seconds,
        low_battery_threshold=settings.low_battery_threshold, cameras_file=settings.cameras_file,
    )

from __future__ import annotations

import os

os.environ.setdefault("EPI_TRACKER_ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.config import get_settings
from app.infrastructure.clock import FakeClock
from app.infrastructure.event_bus import InMemoryEventBus
from app.main import app
from app.observability.metrics import TrackerMetrics
from app.providers.mock_provider import MockTrackerProvider
from app.service import TrackerService

PREFIX = "/api/v1"


@pytest.fixture(autouse=True)
def _reset_state():
    """Cada teste começa com estado limpo — sem isso, o `lru_cache` em
    get_service/get_provider faria os testes compartilharem trackers/áreas
    entre si (mesmo princípio já aprendido nas Fases 3.5-3.7: nunca deixar
    estado vazar entre testes)."""
    get_settings.cache_clear()
    deps.get_service.cache_clear()
    deps.get_provider.cache_clear()
    deps.get_metrics.cache_clear()
    yield
    get_settings.cache_clear()
    deps.get_service.cache_clear()
    deps.get_provider.cache_clear()
    deps.get_metrics.cache_clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def fake_clock() -> FakeClock:
    from datetime import datetime, timezone
    return FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))


@pytest.fixture()
def service(fake_clock) -> TrackerService:
    """Service isolado, com FakeClock — usado nos testes que precisam
    controlar o tempo diretamente (TTL, expiração)."""
    provider = MockTrackerProvider()
    return TrackerService(
        clock=fake_clock, event_bus=InMemoryEventBus(), metrics=TrackerMetrics(), location_provider=provider,
        fresh_seconds=10.0, ttl_seconds=30.0, low_battery_threshold=0.15,
    )

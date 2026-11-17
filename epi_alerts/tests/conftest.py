from __future__ import annotations

import os

os.environ.setdefault("EPI_ALERTS_ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.clock import FakeClock
from app.config import get_settings
from app.main import app
from app.service import AlertService

PREFIX = "/api/v1"


class FakeHttp:
    """Responde por URL. `fail` simula serviço fora do ar."""

    def __init__(self, data=None, fail=False):
        self.data, self.fail = data or {}, fail

    def get(self, url):
        if self.fail:
            raise ConnectionError("fora do ar")
        return self.data[url]


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def svc(clock):
    return AlertService(clock, sync_min_interval=3.0, keep_resolved_seconds=3600)


@pytest.fixture
def client(clock):
    get_settings.cache_clear()
    deps.get_service.cache_clear()
    deps.get_sources.cache_clear()
    service = AlertService(clock, sync_min_interval=0.0)
    app.dependency_overrides[deps.get_service] = lambda: service
    app.dependency_overrides[deps.get_sources] = lambda: []
    yield TestClient(app), service
    app.dependency_overrides.clear()

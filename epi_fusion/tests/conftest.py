import os
import uuid
from datetime import datetime, timezone

os.environ.setdefault("FUS_ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.enums import IdentityStatus, PPEStatus, PPEType
from app.domain.models import Observation, PPEEvidence
from app.fusion import build_fusion_service
from app.identity import InMemoryEmployeeDirectory
from app.infrastructure import FakeClock, InMemoryEventBus
from app.main import app

PREFIX = "/api/v1"
T0 = datetime(2026, 8, 12, 15, 30, 0, tzinfo=timezone.utc)


def make_settings(**over):
    base = dict(
        environment="test",
        fusion_window_seconds=5.0,
        identity_ttl_seconds=3.0,
        state_ttl_seconds=30.0,
        identity_confidence_threshold=0.80,
        required_ppe=["helmet", "vest", "gloves", "boots"],
    )
    base.update(over)
    return Settings(**base)


def make_service(settings=None, clock=None, directory=None):
    settings = settings or make_settings()
    clock = clock or FakeClock()
    directory = directory or InMemoryEmployeeDirectory(active={"FUNC-000234", "FUNC-000111"})
    bus = InMemoryEventBus()
    svc = build_fusion_service(settings, clock=clock, directory=directory, event_bus=bus)
    return svc, clock, bus


def obs(camera, track, employee=None, ppe=None, identity="MATCHED", conf=0.97, ts=None):
    return Observation(
        observation_id=f"OBS-{uuid.uuid4().hex[:8]}",
        camera_id=camera,
        timestamp=ts or T0,
        person_track_id=track,
        identity_status=IdentityStatus(identity),
        identity_confidence=conf,
        employee_id=employee,
        ppe={PPEType(k): PPEEvidence(PPEStatus(v[0]), v[1]) for k, v in (ppe or {}).items()},
    )


@pytest.fixture
def client():
    return TestClient(app)

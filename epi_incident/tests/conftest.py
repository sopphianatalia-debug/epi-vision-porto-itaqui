import os

os.environ.setdefault("INC_ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.enums import OverallStatus, Severity, ViolationType
from app.domain.models import EvaluationInput, ViolationInput
from app.infrastructure import FakeClock, InMemoryEventBus, IncidentRepository
from app.main import app
from app.service import IncidentService

PREFIX = "/api/v1"


def make_service(clock=None):
    settings = Settings(environment="test")
    clock = clock or FakeClock()
    bus = InMemoryEventBus()
    repo = IncidentRepository(settings.id_prefix, settings.id_width, settings.max_history)
    return IncidentService(settings, clock, bus, repo), clock, bus


def viol(employee="FUNC-001", rule="RULE-1", ppe="helmet", severity="HIGH",
         reason_code="PPE_MISSING", reason="helmet ausente", version=3,
         evaluation_id=None, cameras=(), observed="MISSING"):
    return ViolationInput(
        employee_id=employee, rule_id=rule, ppe_type=ppe, reason_code=reason_code,
        reason=reason, severity=Severity(severity), rule_version=version,
        violation_type=ViolationType.PPE_VIOLATION, evaluation_id=evaluation_id,
        observed_status=observed, source_cameras=tuple(cameras),
    )


def evaluation(employee="FUNC-001", status="NON_COMPLIANT", rule="RULE-1",
               violations=(), evaluation_id=None):
    return EvaluationInput(
        employee_id=employee, overall_status=OverallStatus(status),
        effective_rule_id=rule, violations=tuple(violations), evaluation_id=evaluation_id,
    )


@pytest.fixture
def client():
    return TestClient(app)

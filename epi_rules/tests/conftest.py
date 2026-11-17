import os

os.environ.setdefault("RULES_ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.enums import ObservedStatus, Policy, Severity
from app.domain.models import (
    EmployeeSafetyStateInput,
    EvaluationContext,
    PPEObservation,
    PPERequirement,
    SafetyRule,
)
from app.evaluation import build_rules_engine
from app.infrastructure import FakeClock, InMemoryEventBus, RuleRepository
from app.main import app

PREFIX = "/api/v1"


def make_settings(**over):
    base = dict(environment="test", load_seed_rules=True, evaluate_anonymous=False)
    base.update(over)
    return Settings(**base)


def make_engine(settings=None, clock=None, rules=None):
    settings = settings or make_settings()
    clock = clock or FakeClock()
    bus = InMemoryEventBus()
    engine = build_rules_engine(settings, clock=clock, event_bus=bus, rule_repo=rules)
    return engine, clock, bus


def state(ppe, employee="FUNC-000234", area="PATIO_CARGA", operation="MOVIMENTACAO_CARGA",
          role="OPERADOR", identity="MATCHED", eid=None, ts=None):
    ctx = EvaluationContext(employee_id=employee, area=area, operation=operation, role=role,
                            identity_status=identity, timestamp=ts)
    obs = {k: PPEObservation(ObservedStatus(v[0]), v[1]) for k, v in ppe.items()}
    return EmployeeSafetyStateInput(context=ctx, ppe=obs, evaluation_id=eid)


def req(ppe, required=True, **kw):
    return PPERequirement(ppe_type=ppe, required=required, **kw)


def rule(rule_id, requirements, version=1, **kw):
    return SafetyRule(rule_id=rule_id, name=rule_id, version=version,
                      requirements=tuple(requirements), **kw)


@pytest.fixture
def client():
    return TestClient(app)

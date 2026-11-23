import os

os.environ["EPI_JWT_SECRET"] = "segredo-de-teste-com-mais-de-16-caracteres"
os.environ["AUTH_ENVIRONMENT"] = "test"

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.config import get_settings
from app.main import app

PREFIX = "/api/v1"


@pytest.fixture
def client():
    get_settings.cache_clear(); deps.get_service.cache_clear(); deps.get_secret.cache_clear()
    c = TestClient(app)
    svc = deps.get_service()
    svc.create_user("sup", "Supervisora Ana", "SUPERVISOR", "senha-forte-1")
    svc.create_user("oper", "Operador Bruno", "OPERADOR", "senha-forte-2")
    return c


def login(client, user, pwd):
    return client.post(f"{PREFIX}/auth/login", json={"username": user, "password": pwd})


def auth(client, user, pwd):
    return {"Authorization": "Bearer " + login(client, user, pwd).json()["access_token"]}

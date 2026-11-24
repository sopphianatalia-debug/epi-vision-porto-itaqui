"""Nome/cargo/setor do trabalhador: só o supervisor consulta; cadastro fora do ar não quebra nada."""
import io
import json
import urllib.error

import pytest

from app.api.deps import get_workers
from app.config import get_settings
from app.main import app
from app.workers import WorkerDirectory
from tests.conftest import PREFIX
from tests.integration.test_auth_mode import SECRET, tok

ROW = {"employee_code": "FUNC-000001", "name": "Maria Souza", "role_title": "Operadora de guindaste",
       "sector": "CAIS_2", "status": "ACTIVE", "biometric_status": "ENROLLED", "registration": "123"}


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _opener(result):
    def op(req, timeout=None):
        if isinstance(result, Exception):
            raise result
        op.last = req
        return _Resp(json.dumps(result).encode())
    return op


@pytest.fixture
def wk(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "auth_mode", "required")
    monkeypatch.setattr(s, "jwt_secret", SECRET)
    def install(result, url="http://id/api/v1"):
        op = _opener(result)
        app.dependency_overrides[get_workers] = lambda: WorkerDirectory(url, SECRET, opener=op)
        return op
    yield client, install
    app.dependency_overrides.pop(get_workers, None)


def _get(client, role, code="FUNC-000001"):
    return client.get(f"{PREFIX}/workers/{code}", headers=tok(role=role))


def test_supervisor_sees_name_role_sector_and_nothing_biometric(wk):
    client, install = wk
    op = install(ROW)
    r = _get(client, "SUPERVISOR")
    assert r.status_code == 200
    assert r.json() == {"employee_code": "FUNC-000001", "name": "Maria Souza",
                        "role_title": "Operadora de guindaste", "sector": "CAIS_2", "status": "ACTIVE"}
    assert op.last.full_url == "http://id/api/v1/employees/by-code/FUNC-000001"
    assert op.last.get_header("Authorization").startswith("Bearer ")


def test_operator_gets_403_and_no_lookup(wk):
    client, install = wk
    op = install(ROW)
    assert _get(client, "OPERADOR").status_code == 403
    assert not hasattr(op, "last")


def test_requires_login(wk):
    client, install = wk
    install(ROW)
    assert client.get(f"{PREFIX}/workers/FUNC-000001").status_code == 401


def test_unknown_worker_is_404(wk):
    client, install = wk
    install(urllib.error.HTTPError("u", 404, "nf", {}, None))
    assert _get(client, "SUPERVISOR").status_code == 404


def test_registry_down_is_503_not_a_crash(wk):
    client, install = wk
    install(urllib.error.URLError("refused"))
    r = _get(client, "SUPERVISOR")
    assert r.status_code == 503 and "indispon" in r.json()["detail"].lower()


def test_not_configured_is_503(wk):
    client, install = wk
    install(ROW, url="")
    assert _get(client, "SUPERVISOR").status_code == 503

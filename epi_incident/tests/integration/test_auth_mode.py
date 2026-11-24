"""Modo com login (INC_AUTH_MODE=required): leitura e revisão exigem token; o revisor vem do token."""
import time

import jwt
import pytest

from app.config import get_settings
from tests.conftest import PREFIX
from tests.integration.test_api import _body

SECRET = "segredo-de-teste-com-mais-de-16-caracteres"


def tok(username="ana", role="SUPERVISOR", name="Ana Lima", secret=SECRET, exp=3600, iss="epi-auth"):
    now = int(time.time())
    t = jwt.encode({"sub": username, "name": name, "role": role, "iss": iss, "iat": now, "exp": now + exp}, secret, algorithm="HS256")
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture
def secured(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "auth_mode", "required")
    monkeypatch.setattr(s, "jwt_secret", SECRET)
    return client


def _open(client, emp):
    return client.post(f"{PREFIX}/incidents", json=_body(employee_id=emp, evaluation_id="E-" + emp)).json()["incident_id"]


def test_reads_require_login_in_required_mode(secured):
    iid = _open(secured, "F-AUTH-1")                          # abrir (máquina) segue aberto sem chave de serviço
    assert secured.get(f"{PREFIX}/incidents").status_code == 401
    assert secured.get(f"{PREFIX}/incidents/{iid}").status_code == 401
    assert secured.get(f"{PREFIX}/incidents", headers={"Authorization": "Bearer lixo"}).status_code == 401
    assert secured.get(f"{PREFIX}/incidents", headers=tok()).status_code == 200


def test_forged_expired_and_wrong_issuer_tokens_are_rejected(secured):
    for h in (tok(secret="outro-segredo-com-mais-de-16-caracteres"), tok(exp=-10), tok(iss="alguem"), tok(role="ADMIN")):
        assert secured.get(f"{PREFIX}/incidents", headers=h).status_code == 401


def test_review_uses_logged_user_not_body(secured):
    iid = _open(secured, "F-AUTH-2")
    r = secured.post(f"{PREFIX}/incidents/{iid}/review", headers=tok("bruno", "SUPERVISOR", "Bruno"),
                     json={"decision": "CONFIRMED", "note": "sem capacete", "reviewer": "fingindo-ser-outra-pessoa"})
    assert r.status_code == 200
    b = r.json()
    assert b["reviewed_by"] == "bruno" and b["reviewed_by_role"] == "SUPERVISOR" and b["reviewer_verified"] is True
    assert b["review_history"][0]["verified"] is True


def test_review_without_token_is_refused(secured):
    iid = _open(secured, "F-AUTH-3")
    r = secured.post(f"{PREFIX}/incidents/{iid}/review", json={"decision": "CONFIRMED", "note": "x y z", "reviewer": "qualquer"})
    assert r.status_code == 401


def test_only_supervisor_decides_operator_is_read_only(secured):
    iid = _open(secured, "F-AUTH-4")
    body = {"decision": "DISMISSED", "note": "falso positivo"}
    r = secured.post(f"{PREFIX}/incidents/{iid}/review", headers=tok("bruno", "OPERADOR"), json=body)
    assert r.status_code == 403
    assert secured.get(f"{PREFIX}/incidents/{iid}", headers=tok("bruno", "OPERADOR")).json()["review_status"] == "PENDING"   # operador ainda lê
    assert secured.post(f"{PREFIX}/incidents/{iid}/review", headers=tok("ana", "SUPERVISOR"), json=body).status_code == 200
    r = secured.post(f"{PREFIX}/incidents/{iid}/review", headers=tok("carla", "SUPERVISOR"), json={**body, "decision": "CONFIRMED", "note": "confirmo"})
    assert r.status_code == 200 and r.json()["reviewed_by"] == "carla"
    assert [h["reviewer"] for h in r.json()["review_history"]] == ["ana", "carla"]


def test_off_mode_keeps_typed_name_and_marks_unverified(client):
    iid = _open(client, "F-AUTH-5")
    r = client.post(f"{PREFIX}/incidents/{iid}/review", json={"decision": "CONFIRMED", "note": "visto", "reviewer": "digitado"})
    assert r.status_code == 200 and r.json()["reviewer_verified"] is False and r.json()["reviewed_by_role"] is None


def test_service_key_protects_machine_endpoints(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "service_key", "chave-de-servico-secreta")
    assert client.post(f"{PREFIX}/incidents", json=_body(employee_id="F-KEY")).status_code == 401
    assert client.post(f"{PREFIX}/incidents", json=_body(employee_id="F-KEY"), headers={"X-Service-Key": "errada"}).status_code == 401
    assert client.post(f"{PREFIX}/incidents", json=_body(employee_id="F-KEY"), headers={"X-Service-Key": "chave-de-servico-secreta"}).status_code == 201


def test_websocket_requires_token_in_required_mode(secured):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with secured.websocket_connect(f"{PREFIX}/ws/incidents") as ws:
            ws.receive_json()
    good = tok()["Authorization"][7:]
    with secured.websocket_connect(f"{PREFIX}/ws/incidents?token={good}") as ws:
        assert ws.receive_json()["type"] == "SNAPSHOT"

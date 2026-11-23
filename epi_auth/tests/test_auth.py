import time

import jwt

from app.api import deps
from app.security import decode_token, hash_password, issue_token, verify_password
from tests.conftest import PREFIX, auth, login

SECRET = "segredo-de-teste-com-mais-de-16-caracteres"


def test_password_hash_is_salted_and_verifies():
    a, b = hash_password("senha-forte-1"), hash_password("senha-forte-1")
    assert a != b and "senha-forte-1" not in a
    assert verify_password("senha-forte-1", a) and not verify_password("outra", a)
    assert not verify_password("x", "lixo")


def test_login_ok_returns_token_and_public_user(client):
    r = login(client, "sup", "senha-forte-1")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["user"] == {"username": "sup", "name": "Supervisora Ana", "role": "SUPERVISOR", "active": True}
    assert "password" not in str(body)
    claims = decode_token(SECRET, "epi-auth", body["access_token"])
    assert claims["sub"] == "sup" and claims["role"] == "SUPERVISOR"


def test_login_wrong_password_and_unknown_user_look_the_same(client):
    a = login(client, "sup", "errada")
    b = login(client, "ninguem", "qualquer")
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_lockout_after_repeated_failures(client):
    for _ in range(5):
        assert login(client, "oper", "errada").status_code == 401
    r = login(client, "oper", "senha-forte-2")          # até a senha certa é recusada durante o bloqueio
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1


def test_me_requires_valid_token(client):
    assert client.get(f"{PREFIX}/auth/me").status_code == 401
    assert client.get(f"{PREFIX}/auth/me", headers={"Authorization": "Bearer lixo"}).status_code == 401
    assert client.get(f"{PREFIX}/auth/me", headers=auth(client, "oper", "senha-forte-2")).json()["role"] == "OPERADOR"


def test_expired_and_forged_tokens_are_rejected():
    tok, _ = issue_token(SECRET, "epi-auth", 1, "oper", "Op", "OPERADOR")
    assert decode_token(SECRET, "epi-auth", tok) is not None
    assert decode_token("outro-segredo-com-mais-de-16-caracteres", "epi-auth", tok) is None
    assert decode_token(SECRET, "outro-emissor", tok) is None
    expired = jwt.encode({"sub": "oper", "role": "OPERADOR", "iss": "epi-auth", "iat": int(time.time()) - 100, "exp": int(time.time()) - 10}, SECRET, algorithm="HS256")
    assert decode_token(SECRET, "epi-auth", expired) is None
    none_alg = jwt.encode({"sub": "oper", "role": "SUPERVISOR", "iss": "epi-auth", "iat": 1, "exp": int(time.time()) + 999}, None, algorithm="none")
    assert decode_token(SECRET, "epi-auth", none_alg) is None


def test_only_supervisor_manages_users(client):
    op, sup = auth(client, "oper", "senha-forte-2"), auth(client, "sup", "senha-forte-1")
    assert client.get(f"{PREFIX}/users").status_code == 401
    assert client.get(f"{PREFIX}/users", headers=op).status_code == 403
    users = client.get(f"{PREFIX}/users", headers=sup).json()
    assert {u["username"] for u in users} == {"sup", "oper"} and all("password" not in u for u in users)
    new = {"username": "carla", "name": "Carla", "role": "OPERADOR", "password": "outra-senha-9"}
    assert client.post(f"{PREFIX}/users", json=new, headers=op).status_code == 403
    assert client.post(f"{PREFIX}/users", json=new, headers=sup).status_code == 201
    assert client.post(f"{PREFIX}/users", json=new, headers=sup).status_code == 409
    assert login(client, "carla", "outra-senha-9").status_code == 200


def test_user_validation(client):
    sup = auth(client, "sup", "senha-forte-1")
    base = {"username": "dora", "name": "Dora", "role": "OPERADOR", "password": "senha-boa-123"}
    for bad in ({"password": "curta"}, {"role": "ADMIN"}, {"username": "D O"}, {"name": " "}):
        assert client.post(f"{PREFIX}/users", json={**base, **bad}, headers=sup).status_code == 422


def test_deactivated_user_cannot_login_and_old_token_stops_working(client):
    sup = auth(client, "sup", "senha-forte-1")
    op = auth(client, "oper", "senha-forte-2")
    assert client.patch(f"{PREFIX}/users/oper/active", json={"active": False}, headers=sup).status_code == 200
    assert login(client, "oper", "senha-forte-2").status_code == 401
    assert client.get(f"{PREFIX}/auth/me", headers=op).status_code == 401


def test_supervisor_cannot_lock_everyone_out(client):
    sup = auth(client, "sup", "senha-forte-1")
    r = client.patch(f"{PREFIX}/users/sup/active", json={"active": False}, headers=sup)
    assert r.status_code == 422


def test_password_reset(client):
    sup = auth(client, "sup", "senha-forte-1")
    assert client.put(f"{PREFIX}/users/oper/password", json={"password": "nova-senha-77"}, headers=sup).status_code == 200
    assert login(client, "oper", "senha-forte-2").status_code == 401
    assert login(client, "oper", "nova-senha-77").status_code == 200


def test_users_survive_restart_in_sqlite(tmp_path):
    from app.config import Settings
    from app.service import AuthService
    from app.store import UserStore
    db = str(tmp_path / "auth.db")
    AuthService(Settings(), UserStore(db), SECRET).create_user("ana", "Ana", "SUPERVISOR", "senha-forte-1")
    again = AuthService(Settings(), UserStore(db), SECRET)
    assert again.login("ana", "senha-forte-1")["user"]["role"] == "SUPERVISOR"
    assert "senha-forte-1" not in open(db, "rb").read().decode("latin-1")


def test_demo_users_seed_only_when_enabled_and_empty():
    from app.config import Settings
    from app.service import AuthService
    from app.store import UserStore
    off = AuthService(Settings(demo_users=False), UserStore(), SECRET)
    assert off.seed_demo_users() is None
    on = AuthService(Settings(demo_users=True), UserStore(), SECRET)
    pw = on.seed_demo_users()
    assert set(pw) == {"operador", "supervisor"} and on.login("operador", pw["operador"])["user"]["role"] == "OPERADOR"
    assert on.seed_demo_users() is None

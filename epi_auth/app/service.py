"""Regras de login e de usuários. Nada aqui decide conformidade de EPI."""
from __future__ import annotations

import re
import secrets
import time
from typing import Callable, Optional

from app.config import Settings
from app.security import burn_time_like_a_login, hash_password, issue_token, verify_password
from app.store import ROLES, User, UserStore

USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,40}$")


class AuthError(Exception):
    pass


class InvalidCredentials(AuthError):
    pass


class AccountLocked(AuthError):
    def __init__(self, seconds: int) -> None:
        super().__init__(f"muitas tentativas; tente de novo em {seconds}s")
        self.seconds = seconds


class InvalidUser(AuthError):
    pass


class UserExists(AuthError):
    pass


class UserNotFound(AuthError):
    pass


class AuthService:
    def __init__(self, settings: Settings, store: UserStore, secret: str,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._s, self._store, self._secret, self._clock = settings, store, secret, clock
        self._failures: dict[str, tuple[int, float]] = {}      # username -> (erros seguidos, bloqueado até)

    # ------------------------------------------------------------------ login
    def login(self, username: str, password: str) -> dict:
        key = (username or "").strip().lower()
        failed, until = self._failures.get(key, (0, 0.0))
        now = self._clock()
        if until > now:
            raise AccountLocked(int(until - now) + 1)
        user = self._store.get(key)
        if user is None or not user.active:
            burn_time_like_a_login()
            ok = False
        else:
            ok = verify_password(password or "", user.password_hash)
        if not ok:
            failed += 1
            # N erros seguidos bloqueiam o usuário (existente ou não, para não revelar quem existe)
            self._failures[key] = (0, now + self._s.lock_seconds) if failed >= self._s.max_failed_logins else (failed, 0.0)
            raise InvalidCredentials("usuário ou senha inválidos")
        self._failures.pop(key, None)
        token, expires_in = issue_token(self._secret, self._s.issuer, self._s.token_minutes, user.username, user.name, user.role)
        return {"access_token": token, "token_type": "bearer", "expires_in": expires_in, "user": user.public()}

    # --------------------------------------------------------------- usuários
    def _check_password(self, password: str) -> None:
        if len(password or "") < self._s.min_password_length:
            raise InvalidUser(f"a senha precisa ter pelo menos {self._s.min_password_length} caracteres")

    def create_user(self, username: str, name: str, role: str, password: str) -> User:
        username = (username or "").strip().lower()
        if not USERNAME_RE.match(username):
            raise InvalidUser("usuário: 3 a 40 caracteres entre letras minúsculas, números, ponto, hífen ou sublinhado")
        if not (name or "").strip():
            raise InvalidUser("o nome é obrigatório")
        role = (role or "").strip().upper()
        if role not in ROLES:
            raise InvalidUser(f"perfil inválido; use {list(ROLES)}")
        self._check_password(password)
        user = User(username, name.strip(), role, hash_password(password))
        if not self._store.add(user):
            raise UserExists(username)
        return user

    def get_user(self, username: str) -> Optional[User]:
        return self._store.get((username or "").strip().lower())

    def list_users(self) -> list[User]:
        return self._store.list()

    def _get(self, username: str) -> User:
        u = self._store.get((username or "").strip().lower())
        if u is None:
            raise UserNotFound(username)
        return u

    def set_active(self, username: str, active: bool, acting: str) -> User:
        u = self._get(username)
        if not active:
            if u.username == acting:
                raise InvalidUser("você não pode desativar o próprio usuário")
            if u.role == "SUPERVISOR" and not any(x.active and x.role == "SUPERVISOR" and x.username != u.username for x in self._store.list()):
                raise InvalidUser("é preciso manter ao menos um supervisor ativo")
        u.active = active
        self._store.update(u)
        return u

    def reset_password(self, username: str, new_password: str) -> User:
        u = self._get(username)
        self._check_password(new_password)
        u.password_hash = hash_password(new_password)
        self._store.update(u)
        self._failures.pop(u.username, None)
        return u

    def seed_demo_users(self) -> Optional[dict]:
        """Só com AUTH_DEMO_USERS=1 e banco vazio. Senhas aleatórias, devolvidas uma única vez (não ficam em arquivo)."""
        if not self._s.demo_users or self._store.count() > 0:
            return None
        out = {}
        for username, name, role in (("operador", "Operador (demo)", "OPERADOR"), ("supervisor", "Supervisor (demo)", "SUPERVISOR")):
            pwd = secrets.token_urlsafe(9)
            self.create_user(username, name, role, pwd)
            out[username] = pwd
        return out

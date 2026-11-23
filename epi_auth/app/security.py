"""Senha e token. Nunca guarda senha em texto; token é JWT HS256 padrão (outros serviços/Spring conseguem validar)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

import jwt

_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(_N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, dk_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
        dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def burn_time_like_a_login() -> None:
    """Usuário inexistente também gasta o tempo de uma verificação (não revela quem existe)."""
    verify_password("x", _DUMMY_HASH)


def issue_token(secret: str, issuer: str, minutes: int, username: str, name: str, role: str) -> tuple[str, int]:
    now = int(time.time())
    exp = now + minutes * 60
    token = jwt.encode({"sub": username, "name": name, "role": role, "iss": issuer, "iat": now, "exp": exp},
                       secret, algorithm="HS256")
    return token, minutes * 60


def decode_token(secret: str, issuer: str, token: str) -> Optional[dict]:
    """Devolve as claims se o token for válido (assinatura HS256, não expirado, emissor certo); senão None."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], issuer=issuer,
                          options={"require": ["exp", "iat", "sub", "role", "iss"]})
    except jwt.PyJWTError:
        return None

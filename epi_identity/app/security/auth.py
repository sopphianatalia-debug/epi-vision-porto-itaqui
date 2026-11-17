"""Autenticação baseada em JWT."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import jwt

from app.config import get_settings
from app.database import utcnow
from app.enums import Role


@dataclass
class Principal:
    """Identidade autenticada que executa uma ação."""

    subject: str
    role: Role


def create_access_token(subject: str, role: Role) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": subject,
        "role": role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiration_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Principal:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return Principal(subject=payload["sub"], role=Role(payload["role"]))

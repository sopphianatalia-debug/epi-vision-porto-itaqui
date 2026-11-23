"""Quem está chamando. Só LEITURA de token: o login em si é do epi_auth."""
from __future__ import annotations

import hmac
from typing import Optional

import jwt
from fastapi import Header, HTTPException, Query

from app.config import get_settings


def verify_token(token: str) -> Optional[dict]:
    s = get_settings()
    if not s.jwt_secret or len(s.jwt_secret) < 16:
        return None
    try:
        c = jwt.decode(token, s.jwt_secret, algorithms=["HS256"], issuer=s.jwt_issuer,
                       options={"require": ["exp", "iat", "sub", "role", "iss"]})
    except jwt.PyJWTError:
        return None
    if c.get("role") not in ("OPERADOR", "SUPERVISOR"):
        return None
    return {"username": c["sub"], "name": c.get("name") or c["sub"], "role": c["role"]}


def current_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    """None = modo sem login (INC_AUTH_MODE=off). Em 'required', exige Bearer válido."""
    s = get_settings()
    if s.auth_mode != "required":
        return None
    if s.auth_mode == "required" and not s.jwt_secret:
        raise HTTPException(status_code=503, detail="Login exigido, mas EPI_JWT_SECRET não está configurado.")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Entre com usuário e senha.", headers={"WWW-Authenticate": "Bearer"})
    user = verify_token(authorization[7:].strip())
    if user is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.", headers={"WWW-Authenticate": "Bearer"})
    return user


def machine_only(x_service_key: Optional[str] = Header(default=None)) -> None:
    """Endpoints usados por outros serviços (não por pessoas)."""
    key = get_settings().service_key
    if key and not hmac.compare_digest(x_service_key or "", key):
        raise HTTPException(status_code=401, detail="Chave de serviço ausente ou inválida.")

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException

from app.config import get_settings
from app.security import decode_token
from app.service import AuthService
from app.store import UserStore

log = logging.getLogger("epi_auth")


@lru_cache
def get_secret() -> str:
    s = get_settings()
    if s.jwt_secret and len(s.jwt_secret) >= 16:
        return s.jwt_secret
    if s.jwt_secret:
        raise RuntimeError("EPI_JWT_SECRET precisa ter pelo menos 16 caracteres")
    if s.environment == "production":
        raise RuntimeError("Defina EPI_JWT_SECRET (o mesmo valor em todos os serviços).")
    log.warning("EPI_JWT_SECRET não definido: usando segredo temporário. Os outros serviços NÃO conseguirão validar estes tokens.")
    return secrets.token_urlsafe(32)


@lru_cache
def get_service() -> AuthService:
    s = get_settings()
    svc = AuthService(s, UserStore(s.db_path), get_secret())
    created = svc.seed_demo_users()
    if created:
        print("\n=== USUÁRIOS DE DEMONSTRAÇÃO (senhas mostradas só agora) ===")
        for u, p in created.items():
            print(f"  {u}: {p}")
        print("============================================================\n")
    return svc


def current_user(authorization: Optional[str] = Header(default=None), svc: AuthService = Depends(get_service)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Entre com usuário e senha.", headers={"WWW-Authenticate": "Bearer"})
    claims = decode_token(get_secret(), get_settings().issuer, authorization[7:].strip())
    if claims is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.", headers={"WWW-Authenticate": "Bearer"})
    user = svc.get_user(claims["sub"])
    if user is None or not user.active:
        raise HTTPException(status_code=401, detail="Usuário desativado ou inexistente.")
    return {"username": user.username, "name": user.name, "role": user.role}


def supervisor_only(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "SUPERVISOR":
        raise HTTPException(status_code=403, detail="Apenas o supervisor pode fazer isso.")
    return user

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.recognition import FaceRecognitionService, build_recognition_service
from app.security.auth import Principal, decode_token
from app.security.rbac import Permission, has_permission

_bearer = HTTPBearer(auto_error=True)


def get_principal(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> Principal:
    try:
        return decode_token(credentials.credentials)
    except Exception as exc:  # jwt errors -> 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
        ) from exc


def require_permission(permission: Permission):
    def _dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if not has_permission(principal.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Papel {principal.role.value} não possui permissão {permission.value}.",
            )
        return principal

    return _dependency


@lru_cache
def get_recognition_service() -> FaceRecognitionService:
    return build_recognition_service(get_settings())

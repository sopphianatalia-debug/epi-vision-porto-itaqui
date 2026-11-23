from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import current_user, get_service, supervisor_only
from app.service import (AccountLocked, AuthService, InvalidCredentials, InvalidUser, UserExists, UserNotFound)

router = APIRouter()


class LoginIn(BaseModel):
    username: str
    password: str


class UserIn(BaseModel):
    username: str
    name: str
    role: str
    password: str


class ActiveIn(BaseModel):
    active: bool


class PasswordIn(BaseModel):
    password: str


@router.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@router.post("/auth/login", tags=["auth"])
def login(body: LoginIn, svc: AuthService = Depends(get_service)):
    try:
        return svc.login(body.username, body.password)
    except InvalidCredentials as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except AccountLocked as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(exc.seconds)})


@router.get("/auth/me", tags=["auth"])
def me(user: dict = Depends(current_user)):
    return user


@router.get("/users", tags=["users"])
def list_users(_: dict = Depends(supervisor_only), svc: AuthService = Depends(get_service)):
    return [u.public() for u in svc.list_users()]


@router.post("/users", status_code=201, tags=["users"])
def create_user(body: UserIn, _: dict = Depends(supervisor_only), svc: AuthService = Depends(get_service)):
    try:
        return svc.create_user(body.username, body.name, body.role, body.password).public()
    except InvalidUser as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except UserExists:
        raise HTTPException(status_code=409, detail="Já existe um usuário com esse nome.")


@router.patch("/users/{username}/active", tags=["users"])
def set_active(username: str, body: ActiveIn, acting: dict = Depends(supervisor_only), svc: AuthService = Depends(get_service)):
    try:
        return svc.set_active(username, body.active, acting["username"]).public()
    except UserNotFound:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    except InvalidUser as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/users/{username}/password", tags=["users"])
def reset_password(username: str, body: PasswordIn, _: dict = Depends(supervisor_only), svc: AuthService = Depends(get_service)):
    try:
        return svc.reset_password(username, body.password).public()
    except UserNotFound:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    except InvalidUser as exc:
        raise HTTPException(status_code=422, detail=str(exc))

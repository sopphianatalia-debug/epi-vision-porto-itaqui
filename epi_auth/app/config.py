"""Configuração do serviço de login (EPI Vision)."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AUTH_", extra="ignore", populate_by_name=True)

    api_prefix: str = "/api/v1"
    environment: str = "development"

    # Segredo que assina os tokens. É o MESMO que os outros serviços usam para verificar
    # (variável EPI_JWT_SECRET em todos). Nunca vai para o Git.
    jwt_secret: Optional[str] = Field(default=None, validation_alias="EPI_JWT_SECRET")
    token_minutes: int = Field(default=480, gt=0)          # validade do token (8 h = um turno)
    issuer: str = "epi-auth"

    # Caminho do SQLite. Vazio = só em memória (some ao reiniciar).
    db_path: str = ""

    # Bloqueio contra tentativa de senha: N erros seguidos bloqueiam o usuário por X segundos.
    max_failed_logins: int = Field(default=5, gt=0)
    lock_seconds: int = Field(default=60, gt=0)

    min_password_length: int = Field(default=8, ge=6)

    # Cria "operador" e "supervisor" com senha aleatória (mostrada UMA vez no console) se o banco estiver vazio.
    demo_users: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

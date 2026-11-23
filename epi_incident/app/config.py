"""Configuração do Incident Service (Fase 3.4)."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="INC_", extra="ignore", populate_by_name=True)

    app_name: str = "epi-incident-service"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # Prefixo e largura do ID sequencial (INC-000001).
    id_prefix: str = "INC-"
    id_width: int = 6

    # Retenção máxima de histórico em memória (0 = ilimitado).
    max_history: int = 0

    # Login. "off" = sem login (demonstração, como antes). "required" = leitura e revisão exigem token
    # do epi_auth (JWT HS256 assinado com EPI_JWT_SECRET, o mesmo segredo do epi_auth).
    auth_mode: str = "off"
    jwt_secret: Optional[str] = Field(default=None, validation_alias="EPI_JWT_SECRET")
    jwt_issuer: str = "epi-auth"
    # Se definida, os endpoints de MÁQUINA (abrir incidente, avaliações, resolver) exigem o cabeçalho
    # X-Service-Key com este valor. Vazia = abertos (como antes).
    service_key: str = ""

    # Caminho do arquivo SQLite. Vazio = só em memória (comportamento anterior).
    db_path: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

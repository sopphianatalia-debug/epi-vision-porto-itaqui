"""Configuração do Incident Service (Fase 3.4)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="INC_", extra="ignore")

    app_name: str = "epi-incident-service"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # Prefixo e largura do ID sequencial (INC-000001).
    id_prefix: str = "INC-"
    id_width: int = 6

    # Retenção máxima de histórico em memória (0 = ilimitado).
    max_history: int = 0

    # Caminho do arquivo SQLite. Vazio = só em memória (comportamento anterior).
    db_path: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

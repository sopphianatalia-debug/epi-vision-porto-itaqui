"""Configuracao do epi_tracker - mesmo padrao dos outros modulos
(pydantic-settings, prefixo proprio, .env opcional)."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EPI_TRACKER_", extra="ignore")

    environment: str = "development"
    api_prefix: str = "/api/v1"

    # Secao 19 do pedido
    location_fresh_seconds: float = 10.0
    location_ttl_seconds: float = 30.0

    # Arquivo JSON onde o CADASTRO DE CÂMERAS é gravado (o resto do tracker é em memória).
    # Vazio = só em memória (testes). A demo aponta para ~/.epi_vision/cameras.json.
    cameras_file: Optional[str] = None

    # Limiar de bateria baixa (fracao 0-1)
    low_battery_threshold: float = 0.15


@lru_cache
def get_settings() -> Settings:
    return Settings()

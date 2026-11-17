from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EPI_ALERTS_", extra="ignore")

    environment: str = "development"
    api_prefix: str = "/api/v1"

    tracker_url: str = "http://127.0.0.1:8010/api/v1"
    incident_url: str = "http://127.0.0.1:8004/api/v1"
    fusion_url: str = "http://127.0.0.1:8002/api/v1"

    # Intervalo mínimo entre sincronizações automáticas (a UI faz polling).
    sync_min_interval_seconds: float = 3.0
    http_timeout_seconds: float = 2.0
    # Alertas resolvidos mais antigos que isso saem da lista padrão (histórico).
    keep_resolved_seconds: float = 3600.0


@lru_cache
def get_settings() -> Settings:
    return Settings()

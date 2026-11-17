"""Configuração do Rules Engine (Fase 3.3)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="RULES_", extra="ignore")

    app_name: str = "epi-rules-engine"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # Confiança mínima padrão (a regra pode sobrescrever).
    default_minimum_confidence: float = Field(default=0.85, ge=0.0, le=1.0)

    # Debounce/histerese padrão (a regra pode sobrescrever).
    default_min_violation_seconds: float = 0.0
    default_min_recovery_seconds: float = 0.0

    # Comportamento quando não há funcionário identificado.
    evaluate_anonymous: bool = False

    # Carregar regras "seed" de exemplo ao iniciar (pátio de carga etc.).
    load_seed_rules: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()

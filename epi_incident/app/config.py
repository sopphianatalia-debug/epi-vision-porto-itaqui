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

    # Evidência em imagem (recorte da pessoa). Vazio = desativada. Exige INC_AUTH_MODE=required.
    evidence_dir: str = ""
    evidence_days: int = Field(default=30, gt=0)            # após a revisão (ou da captura, se não revisado)
    evidence_days_dismissed: int = Field(default=7, gt=0)   # descartado / evidência insuficiente
    evidence_max_bytes: int = Field(default=1_000_000, gt=0)
    evidence_max_side: int = Field(default=1280, gt=0)      # px; recorte, não o quadro inteiro
    evidence_max_per_incident: int = Field(default=3, gt=0)
    evidence_purge_interval_seconds: int = Field(default=3600, gt=0)

    # Cadastro de trabalhadores (epi_identity, ex.: http://127.0.0.1:8001/api/v1). Vazio = sem nome, só código.
    identity_url: str = ""

    # Caminho do arquivo SQLite. Vazio = só em memória (comportamento anterior).
    db_path: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

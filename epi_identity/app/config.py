"""
Configuração central do Módulo 1 — Identificação Biométrica.

Todos os thresholds e chaves são configuráveis por variáveis de ambiente,
atendendo ao requisito de "threshold configurável" e "modelo configurável".
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EPI_", extra="ignore")

    # --- Aplicação ---
    app_name: str = "epi-identity-module"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # --- Banco de dados ---
    # Ex. prod: postgresql+asyncpg://user:pass@host:5432/epi
    database_url: str = "sqlite+aiosqlite:///./epi_identity.db"

    # --- Segurança / Auth ---
    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Chave Fernet (base64, 32 bytes). Em produção deve vir de um KMS/HSM.
    biometric_encryption_key: str = ""

    # --- Reconhecimento facial ---
    # Provider plugável: "mock" | "insightface" | ...
    face_provider: str = "mock"
    face_model_version: str = "mock-v1"
    embedding_dim: int = 512

    # Qualidade mínima para tentar identificar (0..1)
    quality_threshold: float = Field(default=0.60, ge=0.0, le=1.0)

    # Similaridade mínima (cosseno) para considerar um match candidato
    similarity_threshold: float = Field(default=0.55, ge=-1.0, le=1.0)

    # Confiança mínima para status MATCHED
    confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)

    # Diferença mínima entre 1º e 2º colocado para NÃO ser AMBIGUOUS
    ambiguity_margin: float = Field(default=0.05, ge=0.0, le=1.0)

    # --- Tracking / Reidentificação ---
    # Tempo (s) que uma identidade permanece associada ao track sem novo rosto
    identity_ttl_seconds: int = 30
    # Tempo (s) sem qualquer detecção para encerrar o track
    track_ttl_seconds: int = 15
    # IoU mínimo para associar detecção a track existente
    tracker_iou_threshold: float = Field(default=0.3, ge=0.0, le=1.0)

    # --- Retenção / Privacidade (LGPD) ---
    # Se falso, imagens brutas nunca são persistidas (padrão seguro).
    persist_raw_face_images: bool = False
    embedding_retention_days: int = 365


@lru_cache
def get_settings() -> Settings:
    return Settings()

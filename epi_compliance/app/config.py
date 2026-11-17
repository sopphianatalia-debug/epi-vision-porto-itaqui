"""Configuração do Módulo 3 (tudo por env, nada crítico hardcoded)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CMP_", extra="ignore")

    app_name: str = "epi-compliance-module"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # --- Análise temporal ---
    temporal_window: int = 5          # nº de frames na janela deslizante
    temporal_min_frames: int = 3      # mínimo para conclusão confiável
    high_confidence_agreement: float = Field(default=0.8, ge=0.0, le=1.0)

    # --- Confiança ---
    confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)

    # --- Posicionamento / cobertura ---
    helmet_head_overlap_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    vest_torso_coverage_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    glove_hand_overlap_threshold: float = Field(default=0.15, ge=0.0, le=1.0)
    boots_feet_overlap_threshold: float = Field(default=0.20, ge=0.0, le=1.0)

    # --- Visibilidade ---
    # Margem (fração do frame) para considerar uma região "cortada" pela borda.
    frame_edge_margin: float = Field(default=0.01, ge=0.0, le=0.2)

    # --- Regras: quais EPIs são exigidos ---
    # Chaves válidas: helmet, vest, gloves, boots, glasses
    required_ppe: list[str] = Field(default_factory=lambda: ["helmet", "vest", "gloves", "boots"])

    # --- Provider de pose ---
    pose_provider: str = "heuristic"  # heuristic | yolo

    # --- Evidência / retenção ---
    evidence_max_entries: int = 1000
    evidence_retention_days: int = 90
    # Por padrão NÃO guardamos a imagem, apenas a referência (privacidade/LGPD).
    evidence_store_image: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

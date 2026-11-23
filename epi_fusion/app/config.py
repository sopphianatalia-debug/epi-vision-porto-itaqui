"""Configuração da Fase 3.1 (Fusion Service)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FUS_", extra="ignore")

    app_name: str = "epi-fusion-service"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # EPIs exigidos (para o resumo de evidência — não é conformidade final).
    required_ppe: list[str] = Field(default_factory=lambda: ["helmet", "vest", "gloves", "boots"])

    # Identidade: confiança mínima para aceitar MATCHED como chave.
    identity_confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)

    # Janela de fusão: idade máxima (s) de uma observação para influenciar o estado.
    fusion_window_seconds: float = 5.0
    # Last known state: manter identidade (mesmo track) sem novo MATCH (s).
    identity_ttl_seconds: float = 3.0
    # Expiração do estado consolidado sem novas observações (s).
    state_ttl_seconds: float = 30.0

    # Conflito: diferença mínima de confiança para declarar um vencedor.
    conflict_confidence_margin: float = Field(default=0.15, ge=0.0, le=1.0)

    # Câmera sem observação há mais de N s é considerada OFFLINE (sem sinal) e o WebSocket
    # /fusion/ws/cameras reavalia a cada `ws_poll_seconds`.
    camera_stale_seconds: float = Field(default=30.0, gt=0)
    ws_poll_seconds: float = Field(default=1.0, gt=0)

    # Resolver de identidade (extensível na Fase 3.2).
    identity_resolver: str = "employee_id"


@lru_cache
def get_settings() -> Settings:
    return Settings()

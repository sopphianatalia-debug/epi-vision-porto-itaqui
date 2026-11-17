"""
Configuração do Módulo 2 — Detecção de EPIs.

Nenhum threshold crítico fica hardcoded: todos vêm daqui (env), atendendo à
seção 9 do spec. Modelo também é configurável (seção 3).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PPE_", extra="ignore")

    app_name: str = "epi-ppe-detection-module"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # --- Modelo de detecção (plugável) ---
    detector_provider: str = "mock"          # mock | yolo
    detector_model_path: str = "yolov8n.pt"  # usado pelo provider yolo
    detector_device: str = "auto"            # auto | cpu | cuda
    # Mapa de nomes de classe do modelo -> DetectionClass do sistema, em
    # JSON (Fase 3.7, seção 2). Modelos pré-treinados de EPI publicados por
    # terceiros raramente usam os nomes exatos do projeto (ex.: "hard-hat"
    # em vez de "helmet"). Se vazio, usa só o DEFAULT_NAME_MAP already
    # embutido em app/detection/providers/yolo_provider.py (que já cobre
    # os sinônimos mais comuns). Quando preenchido, MESCLA por cima do
    # default — não precisa repetir as entradas que já funcionam.
    # Exemplo: '{"hard-hat": "HELMET", "no-vest": "SAFETY_VEST"}'
    detector_name_map_json: str = ""

    # --- Thresholds por classe (configuráveis) ---
    default_confidence_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    person_confidence_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    helmet_confidence_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    vest_confidence_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    glove_confidence_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    boots_confidence_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    glasses_confidence_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    ear_confidence_threshold: float = Field(default=0.40, ge=0.0, le=1.0)

    # NMS (supressão de caixas sobrepostas da mesma classe)
    nms_iou_threshold: float = Field(default=0.50, ge=0.0, le=1.0)

    # --- Associação pessoa <-> EPI ---
    # Fração mínima do EPI contida na pessoa para ser candidato.
    association_containment_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    # Score final mínimo para confirmar a associação.
    association_score_threshold: float = Field(default=0.35, ge=0.0, le=1.0)

    # --- Tracking ---
    tracker_iou_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    track_ttl_frames: int = 30  # frames sem detecção antes de encerrar o track

    # --- Avaliação (métricas) ---
    eval_iou_threshold: float = Field(default=0.50, ge=0.0, le=1.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

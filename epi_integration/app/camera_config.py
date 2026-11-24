"""
Configuração centralizada da Fase 3.7 — seção 32 do pedido.

Não duplica nenhuma configuração que já existe nos módulos: os thresholds de
detecção (confidence por classe, NMS, associação, tracking) continuam sendo
responsabilidade exclusiva de `epi_ppe.app.config.Settings` — esta classe só
adiciona o que é específico da camada de integração câmera-pipeline.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CameraPipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EPI_PIPELINE_", extra="ignore")

    # --- Câmera (seção 5) ---
    camera_source: str = "demo"  # "demo" | índice de webcam ("0") | caminho de vídeo | rtsp://...
    camera_id: str = "CAM-01"

    # --- Controle de frequência (seções 17-18) ---
    process_every_n_frames: int = Field(default=5, ge=1)

    # --- Cache de identidade (seção 19) ---
    identity_cache_ttl_seconds: float = Field(default=2.0, ge=0.0)

    # --- Contexto de avaliação (mesmos parâmetros já usados nas Fases 3.5/3.6) ---
    area: str = "PATIO_CARGA"
    operation: str = "MOVIMENTACAO_CARGA"
    role: str = "OPERADOR"

    # --- Modo demonstração (seção 22) ---
    demo_mode: bool = False
    # Seed fixa para um "funcionário de demonstração" pré-cadastrado no
    # epi_identity (provider mock). Sem isso, o pipeline em modo demo nunca
    # vai conseguir MATCHED de verdade, porque o provider mock não deriva
    # identidade do conteúdo da imagem — ver Limitações no README da fase.
    demo_employee_seed: Optional[str] = None
    # DEMO_SCENARIO (Fase 3.7, seção 6): força um cenário controlado de EPI
    # ausente para poder demonstrar NON_COMPLIANT sem depender de tirar o
    # capacete de verdade na frente da câmera. Vazio = desligado (usa só a
    # detecção real). Valores aceitos: "" | "missing_helmet" | "missing_vest"
    # | "missing_gloves" | "missing_boots". Nunca altera o Rules Engine —
    # só o que o Observation Builder relata como observado, exatamente como
    # uma câmera real reportaria uma ausência genuína.
    demo_scenario: str = ""

    # Regiões do corpo que o modelo/câmera NÃO consegue avaliar (CSV), ex.:
    # "feet,hands" para o modelo Roboflow v27, que não tem classes de botas
    # nem luvas. Essas regiões viram NOT_VISIBLE no Fusion em vez de um
    # MISSING falso (EPI não detectado != EPI ausente quando o modelo nem
    # conhece a classe).
    blind_regions: str = ""

    # --- Evidência de localização de EPI (epi_tracker -> Fusion). Opcional ---
    # Vazio = desligado. Ex.: http://127.0.0.1:8010/api/v1
    tracker_url: str = ""
    # area_id (no vocabulário do tracker, ex. "PATIO-02") onde esta câmera
    # está instalada; permite ao Fusion comparar câmera x tracker.
    tracker_area_id: str = ""

    # Evidência em imagem: ao abrir um incidente, envia SÓ o recorte da pessoa ao Incident Service
    # (que também precisa de INC_EVIDENCE_DIR e INC_AUTH_MODE=required). Desligado por padrão.
    send_evidence: bool = False
    # Chave de serviço do Incident (INC_SERVICE_KEY). Vem do ambiente/.env local, nunca do Git.
    incident_service_key: str = ""

    # --- URLs dos serviços já existentes (reaproveitados, não recriados) ---
    vision_url: str = "http://127.0.0.1:8000/api/v1"
    identity_url: str = "http://127.0.0.1:8001/api/v1"
    fusion_url: str = "http://127.0.0.1:8002/api/v1"
    rules_url: str = "http://127.0.0.1:8003/api/v1"
    incident_url: str = "http://127.0.0.1:8004/api/v1"


def resolve_camera_visibility(blind_regions: str) -> Optional[dict[str, bool]]:
    regions = [r.strip() for r in (blind_regions or "").split(",") if r.strip()]
    return {r: False for r in regions} or None


@lru_cache
def get_camera_pipeline_settings() -> CameraPipelineSettings:
    return CameraPipelineSettings()


_DEMO_SCENARIO_OVERRIDES: dict[str, dict[str, dict]] = {
    "missing_helmet": {"helmet": {"status": "MISSING", "confidence": 0.95}},
    "missing_vest": {"vest": {"status": "MISSING", "confidence": 0.95}},
    "missing_gloves": {"gloves": {"status": "MISSING", "confidence": 0.95}},
    "missing_boots": {"boots": {"status": "MISSING", "confidence": 0.95}},
}


def resolve_demo_scenario_override(demo_scenario: str) -> Optional[dict[str, dict]]:
    """Traduz `EPI_PIPELINE_DEMO_SCENARIO` (string simples, fácil de digitar
    num .env) para o dict de override que `RealCameraPipeline(demo_ppe_override=...)`
    espera. Retorna None se `demo_scenario` for vazio ou desconhecido (modo
    silenciosamente desligado, não um erro — evita travar a demo por um
    typo na variável de ambiente)."""
    if not demo_scenario:
        return None
    return _DEMO_SCENARIO_OVERRIDES.get(demo_scenario)

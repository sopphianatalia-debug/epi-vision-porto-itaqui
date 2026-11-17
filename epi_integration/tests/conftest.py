from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.camera_pipeline import RealCameraPipeline  # noqa: E402
from app.clients import FusionClient, IncidentClient, RulesClient, VisionClient  # noqa: E402
from app.identity_client import IdentityClient  # noqa: E402
from app.runner import Pipeline  # noqa: E402


@pytest.fixture(scope="session")
def pipeline():
    with Pipeline() as p:
        yield p


@pytest.fixture(scope="session")
def pipeline_with_vision():
    """Instância SEPARADA da `pipeline` (portas diferentes) que também sobe
    o epi_ppe (Módulo 2) — só usada pelos testes da Fase 3.7
    (test_camera_pipeline.py). As Fases 3.5/3.6 não precisam de visão, então
    ficam na fixture `pipeline` original, mais rápida de subir."""
    with Pipeline(include_vision=True) as p:
        yield p


@pytest.fixture()
def fusion(pipeline) -> FusionClient:
    client = FusionClient(pipeline.fusion.api_url)
    yield client
    client.close()


@pytest.fixture()
def rules(pipeline) -> RulesClient:
    client = RulesClient(pipeline.rules.api_url)
    yield client
    client.close()


@pytest.fixture()
def incident(pipeline) -> IncidentClient:
    client = IncidentClient(pipeline.incident.api_url)
    yield client
    client.close()


@pytest.fixture()
def identity(pipeline) -> IdentityClient:
    """Instância padrão (thresholds default) — MATCHED, UNKNOWN, AMBIGUOUS."""
    client = IdentityClient(pipeline.identity.api_url)
    yield client
    client.close()


@pytest.fixture()
def identity_permissive(pipeline) -> IdentityClient:
    """Instância com EPI_SIMILARITY_THRESHOLD=-1.0 — só para reproduzir
    LOW_CONFIDENCE de forma determinística. Ver docs/contracts.md."""
    client = IdentityClient(pipeline.identity_permissive.api_url)
    yield client
    client.close()


@pytest.fixture()
def full_ppe_ok() -> dict:
    """Conjunto completo de EPIs em conformidade (usado como base nos cenários)."""
    return {
        "helmet": {"status": "DETECTED", "confidence": 0.96},
        "vest": {"status": "DETECTED", "confidence": 0.93},
        "gloves": {"status": "DETECTED", "confidence": 0.94},
        "boots": {"status": "DETECTED", "confidence": 0.91},
    }


# --------------------------------------------------------------------- #
# Fase 3.7 — clientes e pipeline de câmera real (usam pipeline_with_vision,
# não a `pipeline` original).
# --------------------------------------------------------------------- #
@pytest.fixture()
def cam_vision(pipeline_with_vision) -> VisionClient:
    client = VisionClient(pipeline_with_vision.vision.api_url)
    yield client
    client.close()


@pytest.fixture()
def cam_identity(pipeline_with_vision) -> IdentityClient:
    client = IdentityClient(pipeline_with_vision.identity.api_url)
    yield client
    client.close()


@pytest.fixture()
def cam_fusion(pipeline_with_vision) -> FusionClient:
    client = FusionClient(pipeline_with_vision.fusion.api_url)
    yield client
    client.close()


@pytest.fixture()
def cam_rules(pipeline_with_vision) -> RulesClient:
    client = RulesClient(pipeline_with_vision.rules.api_url)
    yield client
    client.close()


@pytest.fixture()
def cam_incident(pipeline_with_vision) -> IncidentClient:
    client = IncidentClient(pipeline_with_vision.incident.api_url)
    yield client
    client.close()


@pytest.fixture()
def camera_pipeline(cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident) -> RealCameraPipeline:
    """RealCameraPipeline com process_every_n_frames=1 por padrão — nos
    testes queremos que TODO frame enviado seja processado (a lógica de
    amostragem em si é testada à parte, com um valor >1 explícito)."""
    return RealCameraPipeline(
        cam_vision, cam_identity, cam_fusion, cam_rules, cam_incident,
        process_every_n_frames=1,
    )

from __future__ import annotations

import itertools

import httpx
import pytest

from app.identity_client import IdentityClient, mint_token

_counter = itertools.count(5000)


def next_seed() -> str:
    return f"SEED-{next(_counter):04d}"


# --------------------------------------------------------------------- #
# 23 — observabilidade
# --------------------------------------------------------------------- #
def test_identity_metrics_increment_on_match(identity):
    before = identity.metrics()
    identity.match(camera_id="CAM-01", seed=next_seed())
    after = identity.metrics()
    assert after["recognition_count"] > before["recognition_count"]
    assert after["unknown"] >= before["unknown"] + 1


def test_fusion_metrics_unaffected_by_identity_errors(identity, fusion):
    """As métricas do Fusion (seção 23 do pedido: 'sem quebrar /fusion/metrics')
    continuam funcionando e não são impactadas por uma falha no Identity."""
    before = fusion.metrics()
    try:
        identity._client.post("/recognition/match", json={"camera_id": "CAM-01"})  # falta "frame"
    except Exception:
        pass
    after = fusion.metrics()
    assert after["observations_total"] == before["observations_total"]  # nada mudou no Fusion
    assert "observations_total" in after  # campo original preservado


# --------------------------------------------------------------------- #
# 26 — tratamento de erros
# --------------------------------------------------------------------- #
def test_match_missing_frame_returns_422(identity):
    resp = identity._client.post("/recognition/match", json={"camera_id": "CAM-01"})
    assert resp.status_code == 422


def test_match_without_token_is_rejected_401(pipeline):
    raw_client = httpx.Client(base_url=pipeline.identity.api_url, timeout=5.0)
    try:
        resp = raw_client.post(
            "/recognition/match",
            json={"camera_id": "CAM-01", "frame": {"faces": [{"seed": next_seed(), "quality": 0.9}]}},
        )
        assert resp.status_code == 401  # HTTPBearer sem header -> 401 (comportamento real do módulo)
    finally:
        raw_client.close()


def test_match_with_invalid_role_is_forbidden(pipeline):
    """VIEWER não tem RECOGNITION_RUN — deve ser barrado (RBAC), mesma regra
    que os testes originais do epi_identity já cobrem para outros endpoints."""
    token = mint_token(subject="viewer-test", role="VIEWER")
    raw_client = httpx.Client(
        base_url=pipeline.identity.api_url, timeout=5.0,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        resp = raw_client.post(
            "/recognition/match",
            json={"camera_id": "CAM-01", "frame": {"faces": [{"seed": next_seed(), "quality": 0.9}]}},
        )
        assert resp.status_code == 403
    finally:
        raw_client.close()


def test_match_low_quality_frame_is_unavailable_not_error(identity):
    """Qualidade insuficiente NÃO é um erro HTTP — é um resultado de domínio
    válido (UNAVAILABLE), documentado desde o Módulo 1: 'nunca produz uma
    identificação de baixa qualidade'."""
    resp = identity._client.post(
        "/recognition/match",
        json={"camera_id": "CAM-01",
              "frame": {"faces": [{"bbox": [0, 0, 100, 100], "seed": next_seed(),
                                    "quality": 0.1, "single_face": True, "face_visible": True}]}},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "UNAVAILABLE"


def test_enroll_nonexistent_employee_returns_404(identity):
    resp = identity._client.post(
        "/employees/EMPLOYEE-DOES-NOT-EXIST/biometric-enrollment",
        json={"frame": {"faces": [{"bbox": [0, 0, 100, 100], "seed": "x", "quality": 0.9,
                                    "single_face": True, "face_visible": True}]}, "consent": True},
    )
    assert resp.status_code == 404


def test_incident_and_rules_stay_healthy_after_identity_error(pipeline, identity, fusion, rules, incident):
    """Uma falha de validação no Identity não corrompe os outros 3 serviços
    (mesmo princípio já verificado na Fase 3.5 para Incident)."""
    identity._client.post("/recognition/match", json={"camera_id": "CAM-01"})  # 422 esperado
    assert httpx.get(f"{pipeline.fusion.base_url}/health").status_code == 200
    assert httpx.get(f"{pipeline.rules.base_url}/health").status_code == 200
    assert httpx.get(f"{pipeline.incident.base_url}/health").status_code == 200
    assert httpx.get(f"{pipeline.identity.base_url}/health").status_code == 200

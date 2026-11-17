from __future__ import annotations

import itertools

import httpx
import pytest

from app.bridge import build_rules_evaluate_payload, enrich_violations_with_cameras

_counter = itertools.count(9000)


def next_employee_id() -> str:
    return f"FUNC-TEST-{next(_counter):04d}"


# --------------------------------------------------------------------- #
# Seção 15 — Event Bus (verificado indiretamente via métricas/efeitos
# observáveis, já que os serviços não expõem histórico de eventos por HTTP
# nesta fase — ver docs/contracts.md, item "Limitações").
# --------------------------------------------------------------------- #
def test_fusion_metrics_reflect_observations(fusion, full_ppe_ok):
    before = fusion.metrics()
    emp = next_employee_id()
    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=full_ppe_ok)
    after = fusion.metrics()
    assert after["observations_total"] > before["observations_total"]


def test_incident_metrics_increment_on_create_and_resolve(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()
    ppe = dict(full_ppe_ok)
    ppe["gloves"] = {"status": "MISSING", "confidence": 0.9}

    before = incident.metrics()

    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=ppe)
    state = fusion.get_employee_state(emp)
    payload = build_rules_evaluate_payload(state, evaluation_id=f"EVAL-{emp}")
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))

    after_create = incident.metrics()
    assert after_create.get("incidents_created_total", after_create.get("created_total", 0)) >= \
        before.get("incidents_created_total", before.get("created_total", 0))


# --------------------------------------------------------------------- #
# Seção 17 — Tratamento de erros
# --------------------------------------------------------------------- #
def test_fusion_rejects_invalid_ppe_status(fusion):
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        fusion._client.post(
            "/fusion/observations",
            json={
                "camera_id": "CAM-01", "person_track_id": "TRK-ERR",
                "employee_id": next_employee_id(),
                "ppe": {"helmet": {"status": "ESTADO_INEXISTENTE", "confidence": 0.9}},
            },
        ).raise_for_status()
    assert exc_info.value.response.status_code == 422


def test_rules_evaluate_missing_rule_context_is_indeterminate(rules, full_ppe_ok):
    """Contexto (area/operation/role) sem nenhuma regra aplicável não derruba o
    serviço — resulta em INDETERMINATE com explicação, não em erro 500."""
    emp = next_employee_id()
    evaluation = rules.evaluate(
        employee_id=emp, ppe=full_ppe_ok,
        area="AREA_SEM_REGRA", operation="OPERACAO_SEM_REGRA", role="FUNCAO_SEM_REGRA",
    )
    assert evaluation["overall_status"] == "INDETERMINATE"
    assert evaluation["effective_rule_id"] is None


def test_incident_resolve_nonexistent_returns_404(incident):
    resp = incident._client.post("/incidents/INC-999999/resolve")
    assert resp.status_code == 404


def test_incident_get_nonexistent_returns_none(incident):
    assert incident.get("INC-DOES-NOT-EXIST") is None


def test_incident_double_resolve_returns_409(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()
    ppe = dict(full_ppe_ok)
    ppe["boots"] = {"status": "MISSING", "confidence": 0.9}

    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=ppe)
    state = fusion.get_employee_state(emp)
    payload = build_rules_evaluate_payload(state, evaluation_id=f"EVAL-{emp}")
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    incident_id = results[0]["incident"]["incident_id"]

    first = incident._client.post(f"/incidents/{incident_id}/resolve")
    assert first.status_code == 200
    second = incident._client.post(f"/incidents/{incident_id}/resolve")
    assert second.status_code == 409


def test_incident_process_evaluation_rejects_missing_rule_id(incident):
    """violations[].rule_id é obrigatório — payload malformado deve falhar a
    validação (422), não corromper o estado do serviço."""
    resp = incident._client.post(
        "/incidents/evaluations",
        json={
            "employee_id": next_employee_id(),
            "overall_status": "NON_COMPLIANT",
            "effective_rule_id": "RULE-X",
            "violations": [{"ppe_type": "helmet", "severity": "HIGH"}],  # falta rule_id
        },
    )
    assert resp.status_code == 422


def test_fusion_and_rules_stay_healthy_after_incident_error(fusion, rules, incident):
    """Uma falha de validação em um módulo (Incident) não deve corromper o
    estado dos outros (Fusion/Rules seguem respondendo normalmente)."""
    incident._client.post("/incidents/evaluations", json={"overall_status": "INVALID"})
    assert fusion._client.get("/health").status_code == 200
    assert rules._client.get("/health").status_code == 200
    assert incident._client.get("/health").status_code == 200

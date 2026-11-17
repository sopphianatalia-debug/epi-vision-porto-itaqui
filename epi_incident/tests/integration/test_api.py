from tests.conftest import PREFIX


def _body(**over):
    b = {
        "employee_id": "FUNC-000234", "rule_id": "RULE-PATIO-CARGA-001",
        "ppe_type": "helmet", "reason_code": "PPE_MISSING",
        "reason": "helmet obrigatório e ausente", "severity": "HIGH",
        "rule_version": 3, "evaluation_id": "EVAL-API-1",
    }
    b.update(over)
    return b


def test_health(client):
    assert client.get(f"{PREFIX}/health").json()["status"] == "ok"


def test_post_creates_incident_201(client):
    r = client.post(f"{PREFIX}/incidents", json=_body(employee_id="FUNC-A", evaluation_id="EA1"))
    assert r.status_code == 201
    data = r.json()
    assert data["action"] == "CREATED"
    assert data["status"] == "OPEN"
    assert data["severity"] == "HIGH"


def test_post_dedup_returns_200(client):
    client.post(f"{PREFIX}/incidents", json=_body(employee_id="FUNC-B", evaluation_id="EB1"))
    r = client.post(f"{PREFIX}/incidents", json=_body(employee_id="FUNC-B", evaluation_id="EB2"))
    assert r.status_code == 200
    assert r.json()["action"] == "UPDATED"
    assert r.json()["occurrence_count"] == 2


def test_get_incident_and_404(client):
    created = client.post(f"{PREFIX}/incidents", json=_body(employee_id="FUNC-C", evaluation_id="EC1")).json()
    got = client.get(f"{PREFIX}/incidents/{created['incident_id']}")
    assert got.status_code == 200
    assert client.get(f"{PREFIX}/incidents/INC-999999").status_code == 404


def test_list_with_filters(client):
    client.post(f"{PREFIX}/incidents", json=_body(employee_id="FUNC-D", ppe_type="gloves",
                                                  severity="MEDIUM", evaluation_id="ED1"))
    r = client.get(f"{PREFIX}/incidents", params={"employee_id": "FUNC-D"})
    assert r.status_code == 200
    assert all(i["employee_id"] == "FUNC-D" for i in r.json())
    r2 = client.get(f"{PREFIX}/incidents", params={"ppe_type": "gloves"})
    assert any(i["ppe_type"] == "gloves" for i in r2.json())


def test_resolve_endpoint_and_conflict(client):
    created = client.post(f"{PREFIX}/incidents", json=_body(employee_id="FUNC-E", evaluation_id="EE1")).json()
    iid = created["incident_id"]
    r = client.post(f"{PREFIX}/incidents/{iid}/resolve")
    assert r.status_code == 200
    assert r.json()["status"] == "RESOLVED"
    # resolver de novo -> 409
    assert client.post(f"{PREFIX}/incidents/{iid}/resolve").status_code == 409


def test_resolve_unknown_404(client):
    assert client.post(f"{PREFIX}/incidents/INC-000000/resolve").status_code == 404


def test_metrics_snapshot(client):
    client.post(f"{PREFIX}/incidents", json=_body(employee_id="FUNC-F", evaluation_id="EF1"))
    m = client.get(f"{PREFIX}/incidents/metrics/snapshot").json()
    assert m["incidents_created"] >= 1
    assert "incidents_by_severity" in m


def test_invalid_payload_422(client):
    # ppe_type vazio -> InvalidViolation -> 422
    assert client.post(f"{PREFIX}/incidents", json=_body(ppe_type="", evaluation_id="EG1")).status_code == 422
    # severity inválida -> validação do Pydantic -> 422
    bad = _body(evaluation_id="EG2")
    bad["severity"] = "SUPER_HIGH"
    assert client.post(f"{PREFIX}/incidents", json=bad).status_code == 422

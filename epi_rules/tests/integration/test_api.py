from tests.conftest import PREFIX


def _payload(**over):
    body = {
        "employee_id": "FUNC-000234", "area": "PATIO_CARGA",
        "operation": "MOVIMENTACAO_CARGA", "role": "OPERADOR",
        "ppe": {
            "helmet": {"status": "DETECTED", "confidence": 0.98},
            "vest": {"status": "DETECTED", "confidence": 0.97},
            "gloves": {"status": "MISSING", "confidence": 0.93},
            "boots": {"status": "DETECTED", "confidence": 0.96},
        },
    }
    body.update(over)
    return body


def test_health(client):
    assert client.get(f"{PREFIX}/health").json()["status"] == "ok"


def test_evaluate_endpoint(client):
    r = client.post(f"{PREFIX}/rules/evaluate", json=_payload())
    assert r.status_code == 200
    data = r.json()
    assert data["overall_status"] == "NON_COMPLIANT"
    assert data["violations"][0]["ppe_type"] == "gloves"
    assert data["explanation"]


def test_get_evaluation_and_employee_compliance(client):
    r = client.post(f"{PREFIX}/rules/evaluate", json=_payload(evaluation_id="EVAL-API-1"))
    eid = r.json()["evaluation_id"]
    got = client.get(f"{PREFIX}/rules/evaluations/{eid}")
    assert got.status_code == 200
    comp = client.get(f"{PREFIX}/rules/employees/FUNC-000234/compliance")
    assert comp.status_code == 200
    assert comp.json()["employee_id"] == "FUNC-000234"


def test_violations_endpoint(client):
    client.post(f"{PREFIX}/rules/evaluate", json=_payload())
    r = client.get(f"{PREFIX}/rules/violations")
    assert r.status_code == 200
    assert any(v["ppe_type"] == "gloves" for v in r.json())


def test_list_and_get_rules(client):
    r = client.get(f"{PREFIX}/rules")
    assert r.status_code == 200
    assert any(rule["rule_id"] == "RULE-PATIO-CARGA-001" for rule in r.json())
    one = client.get(f"{PREFIX}/rules/RULE-PATIO-CARGA-001")
    assert one.status_code == 200


def test_create_update_versions_delete_rule(client):
    new_rule = {
        "rule_id": "RULE-API-TEST", "name": "Regra de teste via API",
        "area": "AREA_API", "requirements": [{"ppe_type": "helmet", "required": True}],
    }
    created = client.post(f"{PREFIX}/rules", json=new_rule)
    assert created.status_code == 200
    assert created.json()["version"] == 1

    # duplicar -> 409
    assert client.post(f"{PREFIX}/rules", json=new_rule).status_code == 409

    # atualizar -> nova versão
    new_rule2 = dict(new_rule)
    new_rule2["requirements"] = [{"ppe_type": "helmet"}, {"ppe_type": "gloves"}]
    updated = client.put(f"{PREFIX}/rules/RULE-API-TEST", json=new_rule2)
    assert updated.json()["version"] == 2

    versions = client.get(f"{PREFIX}/rules/RULE-API-TEST/versions").json()
    assert [v["version"] for v in versions] == [1, 2]

    assert client.delete(f"{PREFIX}/rules/RULE-API-TEST").status_code == 200
    assert client.get(f"{PREFIX}/rules/RULE-API-TEST").status_code == 404


def test_metrics_snapshot(client):
    client.post(f"{PREFIX}/rules/evaluate", json=_payload())
    r = client.get(f"{PREFIX}/rules/metrics/snapshot")
    assert r.status_code == 200
    assert r.json()["rules_evaluated_total"] >= 1


def test_evaluate_not_identified(client):
    r = client.post(f"{PREFIX}/rules/evaluate", json=_payload(employee_id=None, identity_status="NOT_IDENTIFIED"))
    assert r.json()["overall_status"] == "NOT_EVALUATED"

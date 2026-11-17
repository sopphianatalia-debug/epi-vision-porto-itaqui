"""Persistência temporal ponta a ponta: Rules (debounce/histerese) + Incident.

Usa uma regra PRÓPRIA do teste (área exclusiva), para não alterar as regras de
exemplo compartilhadas pelos demais testes da sessão.
"""
from __future__ import annotations

import itertools
import time

import httpx

from app.rules_tuning import apply_persistence

_n = itertools.count(1)
MISSING = {"helmet": {"status": "MISSING", "confidence": 0.95}}
OK = {"helmet": {"status": "DETECTED", "confidence": 0.95}}
VIOL_S = RECOV_S = 1.0


def _make_rule(pipeline) -> tuple[str, str]:
    idx = next(_n)
    rule_id, area = f"RULE-PERSIST-{idx:03d}", f"AREA-PERSIST-{idx:03d}"
    body = {"rule_id": rule_id, "name": "teste persistência", "priority": 500, "area": area,
            "minimum_confidence": 0.5, "requirements": [{"ppe_type": "helmet", "severity": "HIGH"}]}
    r = httpx.post(f"{pipeline.rules.api_url}/rules", json=body, timeout=5)
    r.raise_for_status()
    return rule_id, area


def _step(rules, incident, emp, area, ppe):
    ev = rules.evaluate(employee_id=emp, ppe=ppe, area=area, operation=None, role=None)
    incident.process_evaluation(ev)
    return ev


def test_apply_persistence_creates_new_version(pipeline):
    rule_id, _ = _make_rule(pipeline)
    versions = apply_persistence(pipeline.rules.api_url, (rule_id, "RULE-NAO-EXISTE"), 2.0, 3.0)
    assert versions == {rule_id: 2}
    cur = httpx.get(f"{pipeline.rules.api_url}/rules/{rule_id}", timeout=5).json()
    assert cur["min_violation_seconds"] == 2.0 and cur["min_recovery_seconds"] == 3.0
    assert [r["ppe_type"] for r in cur["requirements"]] == ["helmet"]


def test_brief_missing_does_not_open_incident(pipeline, rules, incident):
    rule_id, area = _make_rule(pipeline)
    apply_persistence(pipeline.rules.api_url, (rule_id,), VIOL_S, RECOV_S)
    emp = f"FUNC-PERSIST-{next(_n):03d}"
    _step(rules, incident, emp, area, MISSING)          # começa a contar
    _step(rules, incident, emp, area, OK)               # voltou antes de 1 s
    assert incident.list(employee_id=emp) == []


def test_sustained_missing_opens_and_sustained_recovery_closes(pipeline, rules, incident):
    rule_id, area = _make_rule(pipeline)
    apply_persistence(pipeline.rules.api_url, (rule_id,), VIOL_S, RECOV_S)
    emp = f"FUNC-PERSIST-{next(_n):03d}"

    _step(rules, incident, emp, area, MISSING)
    assert incident.list(employee_id=emp) == []          # ainda não confirmou
    time.sleep(VIOL_S + 0.3)
    _step(rules, incident, emp, area, MISSING)
    assert len(incident.list(employee_id=emp, status="OPEN")) == 1

    _step(rules, incident, emp, area, OK)                # recuperação começou
    assert len(incident.list(employee_id=emp, status="OPEN")) == 1   # histerese: segue aberto
    time.sleep(RECOV_S + 0.3)
    _step(rules, incident, emp, area, OK)
    assert incident.list(employee_id=emp, status="OPEN") == []
    assert len(incident.list(employee_id=emp, status="RESOLVED")) == 1


def test_flicker_during_missing_does_not_multiply_incidents(pipeline, rules, incident):
    rule_id, area = _make_rule(pipeline)
    apply_persistence(pipeline.rules.api_url, (rule_id,), VIOL_S, RECOV_S)
    emp = f"FUNC-PERSIST-{next(_n):03d}"
    _step(rules, incident, emp, area, MISSING)
    time.sleep(VIOL_S + 0.3)
    _step(rules, incident, emp, area, MISSING)           # incidente aberto
    for ppe in (OK, MISSING, OK, MISSING, OK):           # oscilação rápida
        _step(rules, incident, emp, area, ppe)
    assert len(incident.list(employee_id=emp)) == 1      # um só incidente, sem ruído


def test_min_confidence_override_turns_indeterminate_into_compliant(pipeline, rules):
    """Capacete real com confiança 0,70: com mínimo 0,85 é INDETERMINATE; com 0,60 é COMPLIANT.
    Ausência (MISSING) continua violação nos dois casos."""
    idx = next(_n)
    rule_id, area = f"RULE-CONF-{idx:03d}", f"AREA-CONF-{idx:03d}"
    httpx.post(f"{pipeline.rules.api_url}/rules", timeout=5, json={
        "rule_id": rule_id, "name": "t", "priority": 500, "area": area, "minimum_confidence": 0.85,
        "requirements": [{"ppe_type": "helmet", "severity": "HIGH", "minimum_confidence": 0.85}]}).raise_for_status()
    emp = f"FUNC-CONF-{idx:03d}"
    mid = {"helmet": {"status": "DETECTED", "confidence": 0.70}}
    assert rules.evaluate(employee_id=emp, ppe=mid, area=area, operation=None, role=None)["overall_status"] == "INDETERMINATE"
    apply_persistence(pipeline.rules.api_url, (rule_id,), 0.0, 0.0, min_confidence=0.60)
    emp2 = f"FUNC-CONF2-{idx:03d}"
    assert rules.evaluate(employee_id=emp2, ppe=mid, area=area, operation=None, role=None)["overall_status"] == "COMPLIANT"
    assert rules.evaluate(employee_id=emp2, ppe=MISSING, area=area, operation=None, role=None)["overall_status"] == "NON_COMPLIANT"

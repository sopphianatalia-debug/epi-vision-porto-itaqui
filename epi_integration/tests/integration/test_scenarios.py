"""
Testes de integração ponta-a-ponta da Fase 3.5.

Cada teste usa um employee_id ÚNICO (os serviços vivem por sessão de pytest,
com estado em memória compartilhado entre testes) para não haver
interferência entre cenários.
"""
from __future__ import annotations

import itertools

from app.bridge import build_rules_evaluate_payload, enrich_violations_with_cameras

_counter = itertools.count(1)


def next_employee_id() -> str:
    return f"FUNC-TEST-{next(_counter):04d}"


# --------------------------------------------------------------------- #
# Cenário 1 — funcionário em conformidade
# --------------------------------------------------------------------- #
def test_scenario_1_compliant_flow_no_incident(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()

    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp,
                  ppe={"helmet": full_ppe_ok["helmet"], "gloves": full_ppe_ok["gloves"]})
    fusion.ingest(camera_id="CAM-02", person_track_id="TRK-02", employee_id=emp,
                  ppe={"vest": full_ppe_ok["vest"]})
    fusion.ingest(camera_id="CAM-03", person_track_id="TRK-03", employee_id=emp,
                  ppe={"boots": full_ppe_ok["boots"]})

    state = fusion.get_employee_state(emp)
    assert state["ppe"]["helmet"]["status"] == "DETECTED"
    assert state["ppe"]["vest"]["status"] == "DETECTED"
    assert state["ppe"]["gloves"]["status"] == "DETECTED"
    assert state["ppe"]["boots"]["status"] == "DETECTED"

    payload = build_rules_evaluate_payload(state)
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    assert evaluation["overall_status"] == "COMPLIANT"
    assert evaluation["violations"] == []

    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    assert results == []
    assert incident.list(employee_id=emp) == []


# --------------------------------------------------------------------- #
# Cenário 2 — EPI ausente -> violação -> incidente OPEN
# --------------------------------------------------------------------- #
def test_scenario_2_missing_ppe_opens_incident(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()
    ppe = dict(full_ppe_ok)
    ppe["helmet"] = {"status": "MISSING", "confidence": 0.94}

    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=ppe)
    state = fusion.get_employee_state(emp)
    assert state["ppe"]["helmet"]["status"] == "MISSING"

    payload = build_rules_evaluate_payload(state, evaluation_id=f"EVAL-{emp}")
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    assert evaluation["overall_status"] == "NON_COMPLIANT"
    assert evaluation["evaluation_id"] == f"EVAL-{emp}"

    helmet_violation = next(v for v in evaluation["violations"] if v["ppe_type"] == "helmet")
    assert helmet_violation["rule_id"] == evaluation["effective_rule_id"]
    assert helmet_violation["rule_version"] == 1
    assert helmet_violation["severity"]
    assert helmet_violation["reason"]

    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    assert len(results) == 1
    action, inc = results[0]["action"], results[0]["incident"]
    assert action == "CREATED"
    assert inc["status"] == "OPEN"
    assert inc["employee_id"] == emp
    assert inc["ppe_type"] == "helmet"
    assert inc["rule_id"] == evaluation["effective_rule_id"]
    assert inc["rule_version"] == 1
    assert inc["evaluation_id"] == evaluation["evaluation_id"]
    assert inc["incident_id"].startswith("INC-")


# --------------------------------------------------------------------- #
# Cenário 3 — recuperação: incidente aberto -> COMPLIANT -> RESOLVED
# --------------------------------------------------------------------- #
def test_scenario_3_recovery_resolves_incident(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()
    ppe_missing = dict(full_ppe_ok)
    ppe_missing["helmet"] = {"status": "MISSING", "confidence": 0.94}

    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=ppe_missing)
    state = fusion.get_employee_state(emp)
    payload = build_rules_evaluate_payload(state, evaluation_id=f"EVAL-{emp}-1")
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    incident_id = results[0]["incident"]["incident_id"]
    assert results[0]["incident"]["status"] == "OPEN"

    # Corrige o EPI.
    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=full_ppe_ok)
    state2 = fusion.get_employee_state(emp)
    payload2 = build_rules_evaluate_payload(state2, evaluation_id=f"EVAL-{emp}-2")
    evaluation2 = rules.evaluate(**{k: v for k, v in payload2.items() if k != "ppe"}, ppe=payload2["ppe"])
    assert evaluation2["overall_status"] == "COMPLIANT"

    results2 = incident.process_evaluation(enrich_violations_with_cameras(evaluation2, state2))
    assert len(results2) == 1
    assert results2[0]["action"] == "RESOLVED"
    resolved = results2[0]["incident"]
    assert resolved["incident_id"] == incident_id
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolved_at"] is not None
    assert resolved["duration_seconds"] >= 0
    assert resolved["occurrence_count"] >= 1

    fetched = incident.get(incident_id)
    assert fetched["status"] == "RESOLVED"


# --------------------------------------------------------------------- #
# Cenário 4 — NOT_VISIBLE nunca vira MISSING
# --------------------------------------------------------------------- #
def test_scenario_4_not_visible_is_indeterminate_not_missing(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()
    camera = "CAM-NOFEET-01"

    # Câmera enquadra só a parte superior do corpo: não enxerga os pés.
    fusion.set_visibility_profile(
        camera, {"face": True, "head": True, "torso": True, "hands": True, "feet": False},
    )

    ppe = {k: v for k, v in full_ppe_ok.items() if k != "boots"}  # silêncio sobre boots
    fusion.ingest(camera_id=camera, person_track_id="TRK-01", employee_id=emp, ppe=ppe)
    state = fusion.get_employee_state(emp)
    assert state["ppe"]["boots"]["status"] == "NOT_VISIBLE"

    payload = build_rules_evaluate_payload(state)
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    boots_eval = next(r for res in evaluation["rule_results"] for r in res["requirements"] if r["ppe_type"] == "boots")
    assert boots_eval["result"] == "INDETERMINATE"
    assert boots_eval["reason_code"] == "NOT_VISIBLE"

    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    assert results == []
    assert incident.list(employee_id=emp) == []


# --------------------------------------------------------------------- #
# Cenário 5 — multi-câmera: mesma violação, UM único incidente
# --------------------------------------------------------------------- #
def test_scenario_5_multi_camera_single_incident(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()
    ppe_missing = dict(full_ppe_ok)
    ppe_missing["helmet"] = {"status": "MISSING", "confidence": 0.9}

    for cam in ("CAM-01", "CAM-02", "CAM-03"):
        fusion.ingest(camera_id=cam, person_track_id=f"TRK-{cam}", employee_id=emp, ppe=ppe_missing)

    state = fusion.get_employee_state(emp)
    assert state["ppe"]["helmet"]["status"] == "MISSING"
    assert sorted(state["ppe"]["helmet"]["cameras"]) == ["CAM-01", "CAM-02", "CAM-03"]

    payload = build_rules_evaluate_payload(state, evaluation_id=f"EVAL-{emp}")
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))

    assert len(results) == 1
    inc = results[0]["incident"]
    assert sorted(inc["source_cameras"]) == ["CAM-01", "CAM-02", "CAM-03"]

    all_open = incident.list(employee_id=emp, status="OPEN")
    assert len(all_open) == 1


# --------------------------------------------------------------------- #
# Cenário 6 — duplicação / idempotência
# --------------------------------------------------------------------- #
def test_scenario_6_idempotent_duplicate_evaluation(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()
    ppe_missing = dict(full_ppe_ok)
    ppe_missing["vest"] = {"status": "MISSING", "confidence": 0.9}

    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=ppe_missing)
    state = fusion.get_employee_state(emp)
    eval_id = f"EVAL-{emp}-DUP"
    payload = build_rules_evaluate_payload(state, evaluation_id=eval_id)

    # Mesma avaliação processada duas vezes.
    evaluation_1 = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    evaluation_2 = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    assert evaluation_1 == evaluation_2  # Rules Engine já é idempotente por evaluation_id

    results_1 = incident.process_evaluation(enrich_violations_with_cameras(evaluation_1, state))
    assert results_1[0]["action"] == "CREATED"
    occurrence_after_first = results_1[0]["incident"]["occurrence_count"]

    results_2 = incident.process_evaluation(enrich_violations_with_cameras(evaluation_2, state))
    assert results_2[0]["action"] == "NOOP"
    assert results_2[0]["incident"]["occurrence_count"] == occurrence_after_first
    assert results_2[0]["incident"]["incident_id"] == results_1[0]["incident"]["incident_id"]

    open_incidents = incident.list(employee_id=emp, status="OPEN")
    assert len(open_incidents) == 1


# --------------------------------------------------------------------- #
# Cenário 7 — conflito entre câmeras
# --------------------------------------------------------------------- #
def test_scenario_7_conflicting_cameras_is_indeterminate(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()
    ppe_a = dict(full_ppe_ok)
    ppe_a["helmet"] = {"status": "DETECTED", "confidence": 0.90}
    ppe_b = dict(full_ppe_ok)
    ppe_b["helmet"] = {"status": "MISSING", "confidence": 0.88}  # confiança próxima -> não dá pra resolver

    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=ppe_a)
    fusion.ingest(camera_id="CAM-02", person_track_id="TRK-02", employee_id=emp, ppe=ppe_b)

    state = fusion.get_employee_state(emp)
    assert state["ppe"]["helmet"]["status"] == "UNKNOWN"
    assert state["ppe"]["helmet"].get("conflict") is True

    payload = build_rules_evaluate_payload(state)  # traduz UNKNOWN+conflict -> CONFLICTING
    assert payload["ppe"]["helmet"]["status"] == "CONFLICTING"
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    assert evaluation["overall_status"] == "INDETERMINATE"

    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    assert results == []


# --------------------------------------------------------------------- #
# Cenário 8 — baixa confiança
# --------------------------------------------------------------------- #
def test_scenario_8_low_confidence_is_indeterminate(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()
    ppe = dict(full_ppe_ok)
    ppe["helmet"] = {"status": "DETECTED", "confidence": 0.55}  # < minimum_confidence (0.85)

    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=ppe)
    state = fusion.get_employee_state(emp)

    payload = build_rules_evaluate_payload(state)
    evaluation = rules.evaluate(**{k: v for k, v in payload.items() if k != "ppe"}, ppe=payload["ppe"])
    helmet_eval = next(r for res in evaluation["rule_results"] for r in res["requirements"] if r["ppe_type"] == "helmet")
    assert helmet_eval["result"] == "INDETERMINATE"
    assert helmet_eval["reason_code"] == "LOW_CONFIDENCE"

    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, state))
    assert results == []


# --------------------------------------------------------------------- #
# Cenário 9 — funcionário não identificado
# --------------------------------------------------------------------- #
def test_scenario_9_unidentified_employee_not_evaluated(fusion, rules, incident, full_ppe_ok):
    ingest_result = fusion.ingest(
        camera_id="CAM-01", person_track_id="TRK-ANON-01", employee_id=None, ppe=full_ppe_ok,
    )
    assert ingest_result["employee_id"] is None
    assert ingest_result["kind"] == "anonymous"

    evaluation = rules.evaluate(employee_id=None, ppe=full_ppe_ok, identity_status="NOT_IDENTIFIED")
    assert evaluation["overall_status"] == "NOT_EVALUATED"
    assert evaluation["violations"] == []

    results = incident.process_evaluation(enrich_violations_with_cameras(evaluation, None))
    assert results == []


# --------------------------------------------------------------------- #
# Cenário 10 — nova violação após resolução (EPI diferente)
# --------------------------------------------------------------------- #
def test_scenario_10_new_violation_after_resolution_does_not_reopen_old(fusion, rules, incident, full_ppe_ok):
    emp = next_employee_id()

    # 1) Abre incidente de helmet.
    ppe_1 = dict(full_ppe_ok)
    ppe_1["helmet"] = {"status": "MISSING", "confidence": 0.9}
    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=ppe_1)
    state_1 = fusion.get_employee_state(emp)
    payload_1 = build_rules_evaluate_payload(state_1, evaluation_id=f"EVAL-{emp}-1")
    ev_1 = rules.evaluate(**{k: v for k, v in payload_1.items() if k != "ppe"}, ppe=payload_1["ppe"])
    res_1 = incident.process_evaluation(enrich_violations_with_cameras(ev_1, state_1))
    inc_1_id = res_1[0]["incident"]["incident_id"]
    assert res_1[0]["incident"]["status"] == "OPEN"

    # 2) Corrige helmet -> RESOLVED.
    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=full_ppe_ok)
    state_2 = fusion.get_employee_state(emp)
    payload_2 = build_rules_evaluate_payload(state_2, evaluation_id=f"EVAL-{emp}-2")
    ev_2 = rules.evaluate(**{k: v for k, v in payload_2.items() if k != "ppe"}, ppe=payload_2["ppe"])
    res_2 = incident.process_evaluation(enrich_violations_with_cameras(ev_2, state_2))
    assert res_2[0]["incident"]["incident_id"] == inc_1_id
    assert res_2[0]["incident"]["status"] == "RESOLVED"

    # 3) Nova violação (vest) depois da resolução -> novo incidente, NÃO reabre o INC-1.
    ppe_3 = dict(full_ppe_ok)
    ppe_3["vest"] = {"status": "MISSING", "confidence": 0.9}
    fusion.ingest(camera_id="CAM-01", person_track_id="TRK-01", employee_id=emp, ppe=ppe_3)
    state_3 = fusion.get_employee_state(emp)
    payload_3 = build_rules_evaluate_payload(state_3, evaluation_id=f"EVAL-{emp}-3")
    ev_3 = rules.evaluate(**{k: v for k, v in payload_3.items() if k != "ppe"}, ppe=payload_3["ppe"])
    res_3 = incident.process_evaluation(enrich_violations_with_cameras(ev_3, state_3))

    assert len(res_3) == 1
    inc_2 = res_3[0]["incident"]
    assert inc_2["incident_id"] != inc_1_id
    assert inc_2["ppe_type"] == "vest"
    assert inc_2["status"] == "OPEN"

    # O incidente antigo (helmet) continua RESOLVED — não foi reaberto.
    old = incident.get(inc_1_id)
    assert old["status"] == "RESOLVED"

    all_for_employee = incident.list(employee_id=emp)
    assert len(all_for_employee) == 2

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_engine
from app.api.schemas import EvaluateRequest, RuleIn, rule_to_dict
from app.evaluation import RulesEngine
from app.observability.metrics import metrics

router = APIRouter()


@router.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


# ---------------- Avaliação ----------------
@router.post("/rules/evaluate", tags=["evaluation"])
def evaluate(body: EvaluateRequest, engine: RulesEngine = Depends(get_engine)):
    """Avalia um EmployeeSafetyState (real ou artificial para debug)."""
    evaluation = engine.evaluate(body.to_input())
    return evaluation.to_dict()


@router.get("/rules/evaluations/{evaluation_id}", tags=["evaluation"])
def get_evaluation(evaluation_id: str, engine: RulesEngine = Depends(get_engine)):
    ev = engine.evaluations.get(evaluation_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada.")
    return ev.to_dict()


@router.get("/rules/employees/{employee_id}/compliance", tags=["evaluation"])
def employee_compliance(employee_id: str, engine: RulesEngine = Depends(get_engine)):
    ev = engine.evaluations.latest_for_employee(employee_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Nenhuma avaliação para este funcionário.")
    return ev.to_dict()


@router.get("/rules/violations", tags=["evaluation"])
def violations(limit: int = 50, employee_id: str | None = None, engine: RulesEngine = Depends(get_engine)):
    return [v.to_dict() for v in engine.violations.recent(limit, employee_id)]


# ---------------- CRUD de regras ----------------
@router.get("/rules", tags=["rules"])
def list_rules(engine: RulesEngine = Depends(get_engine)):
    return [rule_to_dict(r) for r in engine.rules.all_latest()]


@router.get("/rules/{rule_id}", tags=["rules"])
def get_rule(rule_id: str, engine: RulesEngine = Depends(get_engine)):
    rule = engine.rules.latest(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    return rule_to_dict(rule)


@router.get("/rules/{rule_id}/versions", tags=["rules"])
def rule_versions(rule_id: str, engine: RulesEngine = Depends(get_engine)):
    versions = engine.rules.versions(rule_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    return [rule_to_dict(r) for r in versions]


@router.post("/rules", tags=["rules"])
def create_rule(body: RuleIn, engine: RulesEngine = Depends(get_engine)):
    if engine.rules.latest(body.rule_id) is not None:
        raise HTTPException(status_code=409, detail="Regra já existe; use PUT para nova versão.")
    rule = engine.rules.save(body.to_domain(version=1))
    return rule_to_dict(rule)


@router.put("/rules/{rule_id}", tags=["rules"])
def update_rule(rule_id: str, body: RuleIn, engine: RulesEngine = Depends(get_engine)):
    current = engine.rules.latest(rule_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    # Nova VERSÃO (as antigas permanecem para auditoria).
    body.rule_id = rule_id
    rule = engine.rules.save(body.to_domain(version=current.version + 1))
    return rule_to_dict(rule)


@router.delete("/rules/{rule_id}", tags=["rules"])
def delete_rule(rule_id: str, engine: RulesEngine = Depends(get_engine)):
    if not engine.rules.delete(rule_id):
        raise HTTPException(status_code=404, detail="Regra não encontrada.")
    return {"deleted": rule_id}


@router.get("/rules/metrics/snapshot", tags=["observability"])
def rules_metrics():
    return metrics.snapshot()

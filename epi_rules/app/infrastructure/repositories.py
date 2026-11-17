"""
Repositórios em memória.

RuleRepository mantém VERSÕES: alterar uma regra cria uma nova versão; as antigas
permanecem para auditoria. EvaluationRepository e ViolationRepository guardam o
histórico imutável.
"""
from __future__ import annotations

from collections import defaultdict, deque

from app.domain.models import ComplianceEvaluation, SafetyRule, Violation


class RuleRepository:
    def __init__(self) -> None:
        # rule_id -> {version -> SafetyRule}
        self._versions: dict[str, dict[int, SafetyRule]] = defaultdict(dict)

    def save(self, rule: SafetyRule) -> SafetyRule:
        self._versions[rule.rule_id][rule.version] = rule
        return rule

    def latest(self, rule_id: str) -> SafetyRule | None:
        versions = self._versions.get(rule_id)
        if not versions:
            return None
        return versions[max(versions)]

    def get_version(self, rule_id: str, version: int) -> SafetyRule | None:
        return self._versions.get(rule_id, {}).get(version)

    def versions(self, rule_id: str) -> list[SafetyRule]:
        return [self._versions[rule_id][v] for v in sorted(self._versions.get(rule_id, {}))]

    def all_latest(self) -> list[SafetyRule]:
        return [self.latest(rid) for rid in self._versions]  # type: ignore[misc]

    def delete(self, rule_id: str) -> bool:
        return self._versions.pop(rule_id, None) is not None


class EvaluationRepository:
    def __init__(self, maxlen: int = 2000) -> None:
        self._by_id: dict[str, ComplianceEvaluation] = {}
        self._order: deque[str] = deque(maxlen=maxlen)
        self._by_employee: dict[str, str] = {}  # última avaliação por funcionário

    def save(self, ev: ComplianceEvaluation) -> None:
        self._by_id[ev.evaluation_id] = ev
        self._order.append(ev.evaluation_id)
        if ev.employee_id:
            self._by_employee[ev.employee_id] = ev.evaluation_id

    def get(self, evaluation_id: str) -> ComplianceEvaluation | None:
        return self._by_id.get(evaluation_id)

    def latest_for_employee(self, employee_id: str) -> ComplianceEvaluation | None:
        eid = self._by_employee.get(employee_id)
        return self._by_id.get(eid) if eid else None

    def exists(self, evaluation_id: str) -> bool:
        return evaluation_id in self._by_id


class ViolationRepository:
    def __init__(self, maxlen: int = 2000) -> None:
        self._violations: deque[Violation] = deque(maxlen=maxlen)

    def add(self, v: Violation) -> None:
        self._violations.append(v)

    def recent(self, limit: int = 50, employee_id: str | None = None) -> list[Violation]:
        items = list(self._violations)
        if employee_id:
            items = [v for v in items if v.employee_id == employee_id]
        return items[-limit:][::-1]

    @property
    def count(self) -> int:
        return len(self._violations)

from app.config import Settings
from app.evaluation.debounce import DebounceTracker
from app.evaluation.engine import RulesEngine
from app.infrastructure import (
    Clock,
    EvaluationRepository,
    InMemoryEventBus,
    RuleRepository,
    ViolationRepository,
)
from app.rules.seed import SEED_RULES


def build_rules_engine(
    settings: Settings,
    clock: Clock | None = None,
    event_bus: InMemoryEventBus | None = None,
    rule_repo: RuleRepository | None = None,
) -> RulesEngine:
    clock = clock or Clock()
    rule_repo = rule_repo or RuleRepository()
    if settings.load_seed_rules and not rule_repo.all_latest():
        for rule in SEED_RULES:
            rule_repo.save(rule)
    return RulesEngine(
        settings=settings,
        clock=clock,
        event_bus=event_bus or InMemoryEventBus(),
        rules=rule_repo,
        evaluations=EvaluationRepository(),
        violations=ViolationRepository(),
        debounce=DebounceTracker(clock),
    )


__all__ = ["RulesEngine", "DebounceTracker", "build_rules_engine"]

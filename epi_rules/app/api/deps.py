from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.evaluation import RulesEngine, build_rules_engine
from app.infrastructure import Clock


@lru_cache
def get_engine() -> RulesEngine:
    return build_rules_engine(get_settings(), clock=Clock())

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.pipeline import PPEPipeline, build_pipeline


@lru_cache
def get_pipeline() -> PPEPipeline:
    return build_pipeline(get_settings())

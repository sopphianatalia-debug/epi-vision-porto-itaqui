from __future__ import annotations

from functools import lru_cache

from app.compliance import PPEComplianceService, build_compliance_service
from app.config import get_settings


@lru_cache
def get_service() -> PPEComplianceService:
    return build_compliance_service(get_settings())

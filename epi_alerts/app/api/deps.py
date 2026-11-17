from __future__ import annotations

from functools import lru_cache

from app.clock import Clock
from app.config import get_settings
from app.service import AlertService
from app.sources import FusionSource, HttpJson, IncidentSource, TrackerSource


@lru_cache
def get_service() -> AlertService:
    s = get_settings()
    return AlertService(Clock(), s.sync_min_interval_seconds, s.keep_resolved_seconds)


@lru_cache
def get_sources():
    s = get_settings()
    http = HttpJson(s.http_timeout_seconds)
    return [TrackerSource(http, s.tracker_url), FusionSource(http, s.fusion_url),
            IncidentSource(http, s.incident_url)]

"""Logs estruturados do Incident Service (sem dados biométricos)."""
from __future__ import annotations

import json
import logging
import sys

from app.domain.enums import EventType

_logger = logging.getLogger("incident")


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.handlers = [handler]
    _logger.setLevel(logging.INFO)


def log_event(event_type: EventType, **fields) -> None:
    for banned in ("embedding", "face", "image", "frame", "biometric", "template"):
        fields.pop(banned, None)
    _logger.info(json.dumps({"event": event_type.value, **fields}, default=str))

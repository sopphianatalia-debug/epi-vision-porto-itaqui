"""
Logs estruturados da fusão.

NUNCA registram dados biométricos (embeddings, imagens). Apenas identificadores
e metadados de decisão.
"""
from __future__ import annotations

import json
import logging
import sys

from app.domain.enums import EventType

_logger = logging.getLogger("fusion")


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.handlers = [handler]
    _logger.setLevel(logging.INFO)


def log_event(event_type: EventType, **fields) -> None:
    # Salvaguarda: remove quaisquer campos sensíveis se acidentalmente passados.
    for banned in ("embedding", "face", "image", "biometric"):
        fields.pop(banned, None)
    _logger.info(json.dumps({"event": event_type.value, **fields}, default=str))

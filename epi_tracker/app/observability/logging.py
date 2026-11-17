"""
Log estruturado - secao 33 do pedido: nunca imagem, embedding, dado
biometrico. Este modulo nem tem acesso a esse tipo de dado (nao fala com
epi_identity), mas o filtro defensivo se mantem pelo mesmo motivo do
epi_ppe/epi_integration.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("epi_tracker")

_FORBIDDEN = {"image", "frame", "embedding", "biometric", "face"}


def log_event(event: str, **fields: Any) -> None:
    safe_fields = {k: v for k, v in fields.items() if k.lower() not in _FORBIDDEN}
    logger.info("%s %s", event, safe_fields)

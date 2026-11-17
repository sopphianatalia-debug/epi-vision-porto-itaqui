"""Domínio dos alertas.

Um alerta NUNCA é uma decisão nova: ele só dá visibilidade a algo que outro
módulo já decidiu (incidente, estado do rastreador, divergência câmera x
rastreador). Não decide conformidade, não cria incidente, não acusa ninguém.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertType(str, Enum):
    INCIDENT_OPEN = "INCIDENT_OPEN"
    PPE_LOCATION_INCONSISTENCY = "PPE_LOCATION_INCONSISTENCY"
    TRACKER_OFFLINE = "TRACKER_OFFLINE"
    TRACKER_LOW_BATTERY = "TRACKER_LOW_BATTERY"
    TRACKER_LOCATION_EXPIRED = "TRACKER_LOCATION_EXPIRED"


@dataclass(frozen=True)
class Condition:
    """Algo que está VERDADE agora, segundo uma fonte. `key` identifica o
    problema (mesmo problema => mesma key => um único alerta)."""

    key: str
    source: str
    type: AlertType
    severity: Severity
    title: str
    message: str
    entity: dict = field(default_factory=dict)


@dataclass
class Alert:
    alert_id: str
    key: str
    source: str
    type: AlertType
    severity: Severity
    status: AlertStatus
    title: str
    message: str
    entity: dict
    opened_at: datetime
    last_seen_at: datetime
    occurrences: int = 1
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    @property
    def active(self) -> bool:
        return self.status != AlertStatus.RESOLVED

    def to_dict(self) -> dict:
        iso = lambda d: d.isoformat() if d else None  # noqa: E731
        return {
            "alert_id": self.alert_id, "key": self.key, "source": self.source,
            "type": self.type.value, "severity": self.severity.value, "status": self.status.value,
            "title": self.title, "message": self.message, "entity": self.entity,
            "opened_at": iso(self.opened_at), "last_seen_at": iso(self.last_seen_at),
            "acknowledged_at": iso(self.acknowledged_at), "resolved_at": iso(self.resolved_at),
            "occurrences": self.occurrences,
        }

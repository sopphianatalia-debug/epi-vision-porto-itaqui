"""Enumerações do Incident Service (Fase 3.4)."""
from __future__ import annotations

from enum import Enum


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ViolationType(str, Enum):
    PPE_VIOLATION = "PPE_VIOLATION"


class OverallStatus(str, Enum):
    """Espelha o ComplianceStatus do Rules Engine (contrato de entrada)."""

    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIAL = "PARTIAL"
    INDETERMINATE = "INDETERMINATE"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"
    NOT_EVALUATED = "NOT_EVALUATED"


# Só uma determinação real permite ABRIR (NON_COMPLIANT) ou RESOLVER (COMPLIANT/
# NON_COMPLIANT) incidentes. Estados inconclusivos não geram nem encerram.
OPENING_STATUS = {OverallStatus.NON_COMPLIANT}
DETERMINED_STATUS = {OverallStatus.COMPLIANT, OverallStatus.NON_COMPLIANT}


class EventType(str, Enum):
    INCIDENT_CREATED = "INCIDENT_CREATED"
    INCIDENT_UPDATED = "INCIDENT_UPDATED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"


class Action(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    RESOLVED = "RESOLVED"
    NOOP = "NOOP"        # idempotente: mesmo evento já aplicado
    IGNORED = "IGNORED"  # entrada não gera incidente (INDETERMINATE etc.)

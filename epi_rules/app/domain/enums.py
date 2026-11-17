"""Enumerações do Rules Engine (Fase 3.3)."""
from __future__ import annotations

from enum import Enum


class ObservedStatus(str, Enum):
    """Status vindo do FusionService (EmployeeSafetyState)."""

    DETECTED = "DETECTED"
    PROPER = "PROPER"
    IMPROPER = "IMPROPER"
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    NOT_VISIBLE = "NOT_VISIBLE"
    NOT_OBSERVED = "NOT_OBSERVED"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


# Status que, por padrão, satisfazem "presença" de um EPI.
DEFAULT_ALLOWED = {ObservedStatus.DETECTED, ObservedStatus.PROPER, ObservedStatus.PRESENT}


class RequirementResult(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    INDETERMINATE = "INDETERMINATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIAL = "PARTIAL"
    INDETERMINATE = "INDETERMINATE"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"
    NOT_EVALUATED = "NOT_EVALUATED"


class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Policy(str, Enum):
    """Como tratar um status não conclusivo."""

    INDETERMINATE = "INDETERMINATE"
    NON_COMPLIANT = "NON_COMPLIANT"
    COMPLIANT = "COMPLIANT"
    IGNORE = "IGNORE"


class IndeterminateRollup(str, Enum):
    """Como agregar quando há itens indeterminados (sem violação)."""

    PARTIAL = "PARTIAL"
    INDETERMINATE = "INDETERMINATE"


class RuleState(str, Enum):
    """Estado da regra aplicada (para o futuro Incident Service)."""

    NOT_EVALUATED = "NOT_EVALUATED"
    COMPLIANT = "COMPLIANT"
    PENDING = "PENDING"        # condição de violação ainda dentro do debounce
    VIOLATION = "VIOLATION"    # violação confirmada (após debounce)
    INDETERMINATE = "INDETERMINATE"
    RESOLVED = "RESOLVED"      # violação recuperada (após histerese)


class ReasonCode(str, Enum):
    OK = "OK"
    MISSING = "MISSING"
    IMPROPER = "IMPROPER"
    NOT_VISIBLE = "NOT_VISIBLE"
    NOT_OBSERVED = "NOT_OBSERVED"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    OPTIONAL_ABSENT = "OPTIONAL_ABSENT"


class EventType(str, Enum):
    RULE_EVALUATION_STARTED = "RULE_EVALUATION_STARTED"
    RULE_EVALUATED = "RULE_EVALUATED"
    COMPLIANCE_STATUS_CHANGED = "COMPLIANCE_STATUS_CHANGED"
    PPE_REQUIREMENT_FAILED = "PPE_REQUIREMENT_FAILED"
    VIOLATION_DETECTED = "VIOLATION_DETECTED"
    VIOLATION_RESOLVED = "VIOLATION_RESOLVED"
    EVALUATION_INDETERMINATE = "EVALUATION_INDETERMINATE"
    LOW_CONFIDENCE_DETECTED = "LOW_CONFIDENCE_DETECTED"
    RULE_CONFLICT = "RULE_CONFLICT"
    RULE_NOT_FOUND = "RULE_NOT_FOUND"
    RULE_EXPIRED = "RULE_EXPIRED"

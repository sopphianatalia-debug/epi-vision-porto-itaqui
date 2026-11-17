"""Enums do domínio do epi_tracker — Fase 3.8."""
from __future__ import annotations

from enum import Enum


class TrackerTechnology(str, Enum):
    MOCK = "MOCK"
    BLE = "BLE"
    RFID = "RFID"
    UWB = "UWB"
    OTHER = "OTHER"


class TrackerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"
    LOW_BATTERY = "LOW_BATTERY"
    UNKNOWN = "UNKNOWN"


class PPEType(str, Enum):
    HELMET = "helmet"
    VEST = "vest"
    BOOTS = "boots"
    GLOVES = "gloves"
    GOGGLES = "goggles"
    HEARING_PROTECTION = "hearing_protection"
    OTHER = "other"


class PPEAssetStatus(str, Enum):
    REGISTERED = "REGISTERED"
    ASSIGNED = "ASSIGNED"
    RETIRED = "RETIRED"


class ObservationStatus(str, Enum):
    """Status de uma TrackerObservation — seção 18 do pedido."""

    DETECTED = "DETECTED"
    NOT_DETECTED = "NOT_DETECTED"
    UNKNOWN = "UNKNOWN"
    EXPIRED = "EXPIRED"


class LocationState(str, Enum):
    """Estado de localização de um tracker em relação ao TTL — seção 19."""

    CURRENT = "CURRENT"        # dentro do TTL, leitura recente
    LAST_KNOWN = "LAST_KNOWN"  # fora do intervalo "fresco" mas ainda dentro do TTL de retenção
    EXPIRED = "EXPIRED"        # além do TTL — não deve ser usado como evidência de localização atual


class SafetyCheckStatus(str, Enum):
    """Mesmo vocabulário do Rules Engine (epi_rules), reaproveitado de
    propósito — o Safety Check REPRESENTA o resultado, nunca decide por
    conta própria (seção 27 do pedido)."""

    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    INDETERMINATE = "INDETERMINATE"
    NOT_EVALUATED = "NOT_EVALUATED"


class InconsistencyType(str, Enum):
    """Seção 20 — inconsistência entre o que a câmera viu e onde o tracker
    do mesmo EPI diz estar. Nunca vira violação sozinha."""

    POSSIBLE_INCONSISTENCY = "POSSIBLE_INCONSISTENCY"

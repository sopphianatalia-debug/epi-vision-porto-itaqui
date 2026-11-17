"""Enumerações do domínio de fusão multi-câmera."""
from __future__ import annotations

from enum import Enum


class IdentityStatus(str, Enum):
    MATCHED = "MATCHED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_IDENTIFIED = "NOT_IDENTIFIED"
    UNKNOWN = "UNKNOWN"


# Somente MATCHED pode ser usado como chave de junção por employee_id.
JOINABLE_IDENTITY = {IdentityStatus.MATCHED}


class PPEType(str, Enum):
    HELMET = "helmet"
    VEST = "vest"
    GLOVES = "gloves"
    BOOTS = "boots"
    GLASSES = "glasses"


class PPEStatus(str, Enum):
    """
    Status de EVIDÊNCIA (não é decisão final de conformidade).

    Distinções obrigatórias:
    - MISSING: câmera COM visibilidade viu a região e o EPI está ausente.
    - NOT_VISIBLE: câmera não consegue ver aquela região (perfil de visibilidade).
    - NOT_OBSERVED: nenhuma câmera reportou informação sobre esse EPI.
    """

    DETECTED = "DETECTED"
    PROPER = "PROPER"
    IMPROPER = "IMPROPER"
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    NOT_VISIBLE = "NOT_VISIBLE"
    NOT_OBSERVED = "NOT_OBSERVED"
    UNKNOWN = "UNKNOWN"


PRESENCE_STATUSES = {PPEStatus.DETECTED, PPEStatus.PROPER, PPEStatus.PRESENT, PPEStatus.IMPROPER}
NON_INFORMATIVE = {PPEStatus.NOT_VISIBLE, PPEStatus.NOT_OBSERVED, PPEStatus.UNKNOWN}


class FusionStatus(str, Enum):
    """Resumo de EVIDÊNCIA consolidada — NÃO é 'conforme/não conforme'."""

    COMPLETE = "COMPLETE"          # todos os EPIs exigidos com presença
    PARTIAL = "PARTIAL"            # parte com presença, parte ausente/não observada
    CONFLICTING = "CONFLICTING"    # há conflito não resolvido entre câmeras
    INSUFFICIENT = "INSUFFICIENT"  # sem evidência suficiente


# Regiões corporais por câmera (perfil de visibilidade) e mapeamento EPI -> região.
class BodyRegionKey(str, Enum):
    FACE = "face"
    HEAD = "head"
    TORSO = "torso"
    HANDS = "hands"
    FEET = "feet"


PPE_REGION = {
    PPEType.HELMET: BodyRegionKey.HEAD,
    PPEType.GLASSES: BodyRegionKey.FACE,
    PPEType.VEST: BodyRegionKey.TORSO,
    PPEType.GLOVES: BodyRegionKey.HANDS,
    PPEType.BOOTS: BodyRegionKey.FEET,
}


class EventType(str, Enum):
    OBSERVATION_RECEIVED = "OBSERVATION_RECEIVED"
    IDENTITY_MATCHED = "IDENTITY_MATCHED"
    IDENTITY_REJECTED = "IDENTITY_REJECTED"
    FUSION_CREATED = "FUSION_CREATED"
    FUSION_UPDATED = "FUSION_UPDATED"
    FUSION_CONFLICT = "FUSION_CONFLICT"
    STATE_EXPIRED = "STATE_EXPIRED"
    ANONYMOUS_OBSERVATION = "ANONYMOUS_OBSERVATION"
    INVALID_EMPLOYEE_ID = "INVALID_EMPLOYEE_ID"

"""
Classes de detecção.

São configuráveis por design: PPE_CLASSES é derivado, não fixo, e novas
classes podem ser adicionadas sem quebrar o pipeline (seção 5 do spec).
"""
from __future__ import annotations

from enum import Enum


class DetectionClass(str, Enum):
    PERSON = "PERSON"
    HELMET = "HELMET"
    SAFETY_VEST = "SAFETY_VEST"
    GLOVES = "GLOVES"
    SAFETY_BOOTS = "SAFETY_BOOTS"
    SAFETY_GLASSES = "SAFETY_GLASSES"
    EAR_PROTECTION = "EAR_PROTECTION"


# Conjunto de classes consideradas EPI (tudo que não é PERSON).
PPE_CLASSES: frozenset[DetectionClass] = frozenset(
    c for c in DetectionClass if c != DetectionClass.PERSON
)


class CameraState(str, Enum):
    CONNECTING = "CONNECTING"
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"

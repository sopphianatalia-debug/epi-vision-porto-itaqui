"""Enumerações do Módulo 3 — verificação de uso correto de EPIs."""
from __future__ import annotations

from enum import Enum


class PPEStatus(str, Enum):
    """
    Estado de um EPI para uma pessoa.

    Distinção CRÍTICA: MISSING (ausente, e a região ESTÁ visível) é diferente
    de NOT_VISIBLE (a câmera não consegue verificar). Nunca afirmar ausência
    quando a região não está visível.
    """

    MISSING = "MISSING"          # região visível, EPI ausente
    PRESENT = "PRESENT"          # detectado, sem julgar posicionamento
    PROPER = "PROPER"            # detectado e corretamente utilizado
    IMPROPER = "IMPROPER"        # detectado, mas mal posicionado (na mão, pendurado...)
    NOT_VISIBLE = "NOT_VISIBLE"  # câmera não consegue verificar a região
    UNKNOWN = "UNKNOWN"          # confiança insuficiente para concluir


class Visibility(str, Enum):
    VISIBLE = "VISIBLE"
    NOT_VISIBLE = "NOT_VISIBLE"


class BodyRegion(str, Enum):
    HEAD = "HEAD"
    EYES = "EYES"
    TORSO = "TORSO"
    LEFT_HAND = "LEFT_HAND"
    RIGHT_HAND = "RIGHT_HAND"
    LEGS = "LEGS"
    FEET = "FEET"


class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"                        # tudo que é exigido está PROPER
    PARTIAL_NON_COMPLIANCE = "PARTIAL_NON_COMPLIANCE"  # parte correta, parte violada
    NON_COMPLIANT = "NON_COMPLIANT"                # nenhum EPI exigido correto
    UNDETERMINED = "UNDETERMINED"                  # sem violação, mas há itens não verificáveis

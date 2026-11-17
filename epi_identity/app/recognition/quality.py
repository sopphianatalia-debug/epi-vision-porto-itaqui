"""
Avaliação de qualidade facial.

Agrega sub-métricas (resolução, iluminação, nitidez, oclusão, pose, número de
rostos) em um FacialQualityScore. Se abaixo do threshold, o pipeline NÃO tenta
identificar — retorna IDENTIFICATION_UNAVAILABLE em vez de um palpite ruim.
"""
from __future__ import annotations

from app.recognition.types import FaceQuality


class QualityGate:
    def __init__(self, threshold: float) -> None:
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        return self._threshold

    def passes(self, quality: FaceQuality) -> bool:
        """Reprova cedo se qualquer condição eliminatória falhar."""
        if not quality.single_face:
            return False
        if not quality.face_visible:
            return False
        return quality.score >= self._threshold

    def rejection_reasons(self, quality: FaceQuality) -> list[str]:
        reasons: list[str] = list(quality.reasons)
        if not quality.single_face:
            reasons.append("multiple_or_no_faces")
        if not quality.face_visible:
            reasons.append("face_not_visible")
        if quality.score < self._threshold:
            reasons.append(f"quality_below_threshold({quality.score:.2f}<{self._threshold:.2f})")
        return reasons

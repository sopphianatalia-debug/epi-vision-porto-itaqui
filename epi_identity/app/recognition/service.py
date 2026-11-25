"""
FaceRecognitionService — orquestrador de domínio.

Implementa a interface conceitual do spec:
    detectFace, assessFaceQuality, generateEmbedding, compareEmbedding, identifyEmployee

É agnóstico a banco e a HTTP: recebe um frame e uma galeria (em memória) e
devolve um IdentificationResult. A persistência fica na camada de aplicação.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from app.enums import RecognitionStatus
from app.recognition.base import FaceRecognitionProvider
from app.recognition.image import InvalidImageError
from app.recognition.matching import MatchingEngine
from app.recognition.quality import QualityGate
from app.recognition.types import (
    DetectedFace,
    FaceEmbedding,
    IdentificationResult,
)


class QualityTooLowError(Exception):
    """Rosto sem qualidade suficiente para cadastro biométrico."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


class FaceRecognitionService:
    def __init__(
        self,
        provider: FaceRecognitionProvider,
        quality_gate: QualityGate,
        matching_engine: MatchingEngine,
    ) -> None:
        self._provider = provider
        self._quality = quality_gate
        self._matcher = matching_engine

    @property
    def model_version(self) -> str:
        return self._provider.model_version

    # --- primitivas ---
    def detect_faces(self, frame: Any) -> list[DetectedFace]:
        return self._provider.detect_faces(frame)

    def best_face(self, frame: Any) -> Optional[DetectedFace]:
        faces = self._provider.detect_faces(frame)
        if not faces:
            return None
        return max(faces, key=lambda f: f.quality.score)

    # --- cadastro biométrico ---
    def generate_enrollment_embedding(self, frame: Any) -> FaceEmbedding:
        try:
            face = self.best_face(frame)
        except InvalidImageError as exc:
            raise QualityTooLowError([f"invalid_image: {exc}"]) from exc
        if face is None:
            raise QualityTooLowError(["no_face_detected"])
        if not self._quality.passes(face.quality):
            raise QualityTooLowError(self._quality.rejection_reasons(face.quality))
        return self._provider.generate_embedding(frame, face)

    # --- identificação (pipeline completo) ---
    def identify(
        self,
        frame: Any,
        gallery: list[tuple[str, Sequence[float]]],
    ) -> IdentificationResult:
        try:
            face = self.best_face(frame)
        except InvalidImageError:
            return IdentificationResult(status=RecognitionStatus.UNAVAILABLE, requires_review=False)
        if face is None:
            return IdentificationResult(status=RecognitionStatus.UNAVAILABLE, requires_review=False)

        # Gate de qualidade: abaixo do limiar -> UNAVAILABLE (não "chuta").
        if not self._quality.passes(face.quality):
            return IdentificationResult(
                status=RecognitionStatus.UNAVAILABLE,
                quality_score=face.quality.score,
                model_version=self._provider.model_version,
            )

        embedding = self._provider.generate_embedding(frame, face)
        return self._matcher.match(
            probe=embedding.vector,
            gallery=gallery,
            model_version=embedding.model_version,
            quality_score=embedding.quality_score,
        )

    def compare_embedding(
        self,
        probe: Sequence[float],
        gallery: list[tuple[str, Sequence[float]]],
        quality_score: float,
    ) -> IdentificationResult:
        return self._matcher.match(
            probe=probe,
            gallery=gallery,
            model_version=self._provider.model_version,
            quality_score=quality_score,
        )

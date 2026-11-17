"""Estruturas de dados imutáveis do domínio de reconhecimento."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.enums import RecognitionStatus


@dataclass(frozen=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


@dataclass(frozen=True)
class FaceQuality:
    """Sub-métricas de qualidade + score agregado (FacialQualityScore)."""

    score: float
    resolution_ok: bool = True
    illumination_ok: bool = True
    sharpness_ok: bool = True
    face_visible: bool = True
    single_face: bool = True
    occlusion_ok: bool = True
    pose_ok: bool = True
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DetectedFace:
    bbox: BoundingBox
    quality: FaceQuality


@dataclass(frozen=True)
class FaceEmbedding:
    vector: tuple[float, ...]
    model_version: str
    quality_score: float


@dataclass(frozen=True)
class Candidate:
    employee_code: str
    similarity: float


@dataclass(frozen=True)
class IdentificationResult:
    """Resultado final da identificação, pronto para persistir e para o Módulo de EPI."""

    status: RecognitionStatus
    employee_code: Optional[str] = None
    similarity_score: Optional[float] = None
    confidence_score: Optional[float] = None
    quality_score: Optional[float] = None
    runner_up: Optional[Candidate] = None
    model_version: Optional[str] = None
    requires_review: bool = False

    def to_epi_contract(self, camera_id: str, person_track_id: str, timestamp: str) -> dict:
        """Contrato consumido futuramente pelo Módulo de EPI (seção 17)."""
        return {
            "camera_id": camera_id,
            "person_track_id": person_track_id,
            "employee_id": self.employee_code,
            "identity_status": self.status.value,
            "confidence": self.confidence_score,
            "timestamp": timestamp,
        }

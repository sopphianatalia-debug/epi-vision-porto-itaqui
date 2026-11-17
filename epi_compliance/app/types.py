"""Estruturas de dados do domínio de conformidade."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.enums import BodyRegion, ComplianceStatus, PPEStatus, Visibility
from app.geometry import BoundingBox


@dataclass(frozen=True)
class PPEObservation:
    """Um EPI detectado e já associado à pessoa (saída do Módulo 2)."""

    ppe_type: str          # "helmet" | "vest" | "gloves" | "glasses" | "boots"
    bbox: BoundingBox
    confidence: float
    association_score: float = 1.0


@dataclass
class PersonObservation:
    """Entrada de um frame: uma pessoa rastreada + seus EPIs + contexto da câmera."""

    person_track_id: str
    person_bbox: BoundingBox
    frame_width: float
    frame_height: float
    ppe: list[PPEObservation] = field(default_factory=list)
    employee_id: Optional[str] = None
    camera_id: str = "CAM-UNKNOWN"
    frame_reference: Optional[str] = None
    # Override opcional de visibilidade por região (útil quando há pose real).
    visible_regions: Optional[dict[BodyRegion, Visibility]] = None


@dataclass(frozen=True)
class FrameAssessment:
    """Avaliação de um EPI em UM frame (antes da agregação temporal)."""

    status: PPEStatus
    confidence: float
    reason: str = ""


@dataclass(frozen=True)
class PPEResult:
    """Resultado de um EPI após agregação temporal."""

    status: PPEStatus
    confidence: float
    note: str = ""

    def to_dict(self) -> dict:
        d = {"status": self.status.value, "confidence": round(self.confidence, 4)}
        if self.note:
            d["note"] = self.note
        return d


@dataclass
class ComplianceResult:
    person_track_id: str
    employee_id: Optional[str]
    camera_id: str
    timestamp: str
    helmet: PPEResult
    vest: PPEResult
    glove_left: PPEResult
    glove_right: PPEResult
    glasses: PPEResult
    boots: PPEResult
    overall: ComplianceStatus

    def gloves_summary(self) -> str:
        visible = [g for g in (self.glove_left, self.glove_right)
                   if g.status != PPEStatus.NOT_VISIBLE]
        proper = [g for g in visible if g.status in (PPEStatus.PROPER, PPEStatus.PRESENT)]
        if not visible:
            return "not_verifiable"
        return f"{len(proper)}/{len(visible)}"

    def to_dict(self) -> dict:
        return {
            "person_track_id": self.person_track_id,
            "employee_id": self.employee_id,
            "camera_id": self.camera_id,
            "timestamp": self.timestamp,
            "helmet": self.helmet.to_dict(),
            "vest": self.vest.to_dict(),
            "gloves": {
                "left": self.glove_left.status.value,
                "right": self.glove_right.status.value,
                "summary": self.gloves_summary(),
            },
            "glasses": self.glasses.to_dict(),
            "boots": self.boots.to_dict(),
            "overall": self.overall.value,
        }

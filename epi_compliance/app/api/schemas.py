from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.enums import BodyRegion, Visibility
from app.geometry import BoundingBox
from app.types import PersonObservation, PPEObservation


class PPEIn(BaseModel):
    ppe_type: str = Field(examples=["helmet"])
    bbox: list[float]
    confidence: float = 0.9
    association_score: float = 1.0


class FrameIn(BaseModel):
    person_track_id: str = Field(examples=["TRACK-000123"])
    person_bbox: list[float]
    frame_width: float = 1280
    frame_height: float = 720
    ppe: list[PPEIn] = Field(default_factory=list)
    employee_id: Optional[str] = None
    camera_id: str = "CAM-07"
    frame_reference: Optional[str] = None
    visible_regions: Optional[dict[BodyRegion, Visibility]] = None

    def to_observation(self) -> PersonObservation:
        return PersonObservation(
            person_track_id=self.person_track_id,
            person_bbox=BoundingBox(*self.person_bbox),
            frame_width=self.frame_width,
            frame_height=self.frame_height,
            ppe=[
                PPEObservation(p.ppe_type, BoundingBox(*p.bbox), p.confidence, p.association_score)
                for p in self.ppe
            ],
            employee_id=self.employee_id,
            camera_id=self.camera_id,
            frame_reference=self.frame_reference,
            visible_regions=self.visible_regions,
        )


class EvaluateResponse(BaseModel):
    result: dict
    dashboard: dict
    evidence: list[dict]


class BatchRequest(BaseModel):
    frames: list[FrameIn]


class BatchResponse(BaseModel):
    final: dict
    dashboard: dict
    frames_processed: int
    evidence: list[dict]

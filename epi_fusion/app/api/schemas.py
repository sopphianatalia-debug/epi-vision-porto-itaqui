from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.enums import BodyRegionKey, IdentityStatus, PPEStatus, PPEType


class PPEEvidenceIn(BaseModel):
    status: PPEStatus
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class ObservationIn(BaseModel):
    camera_id: str = Field(examples=["CAM-01"])
    person_track_id: str = Field(examples=["TRACK-000001"])
    identity_status: IdentityStatus = IdentityStatus.MATCHED
    identity_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    employee_id: Optional[str] = Field(default=None, examples=["FUNC-000234"])
    ppe: dict[PPEType, PPEEvidenceIn] = Field(default_factory=dict)
    timestamp: Optional[datetime] = None
    observation_id: Optional[str] = None


class IngestOut(BaseModel):
    employee_id: Optional[str]
    identity_status: str
    kind: str
    reason: str


class VisibilityProfileIn(BaseModel):
    visibility: dict[BodyRegionKey, bool]


class VisibilityProfileOut(BaseModel):
    camera_id: str
    visibility: dict[str, bool]


class CameraHealthOut(BaseModel):
    camera_id: str
    observations: int
    identity_matches: int
    identity_match_rate: Optional[float]
    anonymous: int
    conflicts: int
    avg_confidence: Optional[float]
    not_visible: int
    not_visible_rate: Optional[float]
    health_score: Optional[float]


class CameraHealthList(BaseModel):
    cameras: list[CameraHealthOut]

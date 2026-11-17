from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.enums import RecognitionStatus, ReviewDecision


class MatchRequest(BaseModel):
    camera_id: str
    person_track_id: Optional[str] = None
    frame: dict  # cena (mock) ou payload de imagem decodificável pelo provider


class MatchResponse(BaseModel):
    event_id: str
    camera_id: str
    person_track_id: Optional[str]
    employee_id: Optional[str]
    status: RecognitionStatus
    similarity_score: Optional[float]
    confidence: Optional[float]
    quality_score: Optional[float]
    requires_review: bool
    model_version: Optional[str]
    timestamp: datetime


class RecognitionEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    camera_id: str
    employee_code: Optional[str]
    status: str
    quality_score: Optional[float]
    similarity_score: Optional[float]
    confidence_score: Optional[float]
    requires_review: bool
    model_version: Optional[str]
    created_at: datetime


class ReviewRequest(BaseModel):
    event_id: str
    decision: ReviewDecision
    final_employee_code: Optional[str] = None
    notes: Optional[str] = None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    decision: str
    reviewer: str
    final_employee_code: Optional[str]
    created_at: datetime

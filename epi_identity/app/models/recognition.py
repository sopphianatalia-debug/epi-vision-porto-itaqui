from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.enums import RecognitionStatus, TrackState


class PersonTrack(Base):
    """
    Identificador TEMPORÁRIO da pessoa rastreada — NÃO é a identidade real.
    Ex.: CAM07_PERSON_00127. A identidade real (employee_code) só é anexada
    após reconhecimento confirmado.
    """

    __tablename__ = "person_tracks"

    track_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    camera_id: Mapped[str] = mapped_column(String(50), index=True)
    state: Mapped[str] = mapped_column(String(20), default=TrackState.ACTIVE.value)

    # Identidade associada (pode ser nula = ainda desconhecida)
    employee_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    identity_status: Mapped[str] = mapped_column(
        String(20), default=RecognitionStatus.UNKNOWN.value
    )
    identity_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class FaceRecognitionEvent(Base):
    """Registro de cada tentativa de identificação (auditável e observável)."""

    __tablename__ = "face_recognition_events"

    camera_id: Mapped[str] = mapped_column(String(50), index=True)
    person_track_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("person_tracks.id"), nullable=True, index=True
    )

    employee_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # RecognitionStatus

    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Segundo colocado (para análise de ambiguidade), sem PII adicional.
    runner_up_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    runner_up_similarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    processing_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class RecognitionReview(Base):
    """Decisão de revisão humana sobre um evento (a IA não é autoridade absoluta)."""

    __tablename__ = "recognition_reviews"

    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("face_recognition_events.id"), index=True
    )
    decision: Mapped[str] = mapped_column(String(20))  # ReviewDecision
    reviewer: Mapped[str] = mapped_column(String(100))
    final_employee_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_recognition_service, require_permission
from app.database import get_session
from app.models import FaceRecognitionEvent
from app.observability.metrics import metrics
from app.recognition import FaceRecognitionService
from app.schemas.recognition import (
    MatchRequest,
    MatchResponse,
    RecognitionEventOut,
    ReviewOut,
    ReviewRequest,
)
from app.security.auth import Principal
from app.security.rbac import Permission
from app.services import recognition_service, review_service

router = APIRouter(prefix="/recognition", tags=["recognition"])


@router.post("/match", response_model=MatchResponse)
async def match(
    body: MatchRequest,
    session: AsyncSession = Depends(get_session),
    recognition: FaceRecognitionService = Depends(get_recognition_service),
    actor: Principal = Depends(require_permission(Permission.RECOGNITION_RUN)),
):
    event, result = await recognition_service.run_match(
        session,
        camera_id=body.camera_id,
        frame=body.frame,
        recognition=recognition,
        actor=actor,
        person_track_id=body.person_track_id,
    )
    return MatchResponse(
        event_id=event.id,
        camera_id=event.camera_id,
        person_track_id=body.person_track_id,
        employee_id=result.employee_code,
        status=result.status,
        similarity_score=result.similarity_score,
        confidence=result.confidence_score,
        quality_score=result.quality_score,
        requires_review=result.requires_review,
        model_version=result.model_version,
        timestamp=event.created_at,
    )


@router.get("/events", response_model=list[RecognitionEventOut])
async def list_events(
    limit: int = Query(default=50, le=200),
    requires_review: bool | None = None,
    session: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_permission(Permission.RECOGNITION_READ)),
):
    stmt = select(FaceRecognitionEvent).order_by(FaceRecognitionEvent.created_at.desc()).limit(limit)
    if requires_review is not None:
        stmt = stmt.where(FaceRecognitionEvent.requires_review.is_(requires_review))
    rows = await session.scalars(stmt)
    return list(rows)


@router.get("/events/{event_id}", response_model=RecognitionEventOut)
async def get_event(
    event_id: str,
    session: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_permission(Permission.RECOGNITION_READ)),
):
    event = await session.get(FaceRecognitionEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    return event


@router.post("/review", response_model=ReviewOut)
async def review(
    body: ReviewRequest,
    session: AsyncSession = Depends(get_session),
    actor: Principal = Depends(require_permission(Permission.REVIEW_DECIDE)),
):
    try:
        return await review_service.submit_review(
            session,
            event_id=body.event_id,
            decision=body.decision,
            reviewer=actor,
            final_employee_code=body.final_employee_code,
            notes=body.notes,
        )
    except review_service.EventNotFound:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")


@router.get("/metrics")
async def recognition_metrics(
    _: Principal = Depends(require_permission(Permission.RECOGNITION_READ)),
):
    return metrics.snapshot()

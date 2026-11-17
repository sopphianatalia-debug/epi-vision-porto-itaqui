from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditAction, ReviewDecision
from app.models import FaceRecognitionEvent, RecognitionReview
from app.security.auth import Principal
from app.services.audit_service import record_audit


class EventNotFound(Exception):
    pass


async def submit_review(
    session: AsyncSession,
    event_id: str,
    decision: ReviewDecision,
    reviewer: Principal,
    final_employee_code: str | None = None,
    notes: str | None = None,
) -> RecognitionReview:
    event = await session.get(FaceRecognitionEvent, event_id)
    if event is None:
        raise EventNotFound(event_id)

    review = RecognitionReview(
        event_id=event.id,
        decision=decision.value,
        reviewer=reviewer.subject,
        final_employee_code=final_employee_code,
        notes=notes,
    )
    session.add(review)

    # A decisão humana prevalece sobre a IA.
    if decision == ReviewDecision.CONFIRM and final_employee_code:
        event.employee_code = final_employee_code
    elif decision == ReviewDecision.REJECT or decision == ReviewDecision.MARK_UNKNOWN:
        event.employee_code = None
    event.requires_review = False

    await record_audit(
        session,
        AuditAction.REVIEW_DECISION,
        actor=reviewer.subject,
        actor_role=reviewer.role.value,
        resource_type="recognition_event",
        resource_id=event.id,
        details={"decision": decision.value, "final": final_employee_code},
    )
    await session.commit()
    await session.refresh(review)
    return review

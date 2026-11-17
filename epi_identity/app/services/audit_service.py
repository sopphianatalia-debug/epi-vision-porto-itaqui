from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditAction
from app.models import AuditLog


async def record_audit(
    session: AsyncSession,
    action: AuditAction,
    actor: str,
    actor_role: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    log = AuditLog(
        action=action.value,
        actor=actor,
        actor_role=actor_role,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    session.add(log)
    await session.flush()
    return log

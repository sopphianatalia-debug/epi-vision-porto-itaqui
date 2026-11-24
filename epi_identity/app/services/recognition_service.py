from __future__ import annotations

import logging
import time
from typing import Optional, Sequence

from cryptography.fernet import InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditAction, BiometricStatus, EmployeeStatus, RecognitionStatus
from app.models import Employee, EmployeeBiometric, FaceRecognitionEvent
from app.observability.metrics import metrics
from app.recognition import FaceRecognitionService
from app.recognition.types import IdentificationResult
from app.security.auth import Principal
from app.security.crypto import decrypt_embedding
from app.services.audit_service import record_audit

logger = logging.getLogger(__name__)


async def load_gallery(session: AsyncSession) -> list[tuple[str, Sequence[float]]]:
    """
    Carrega a galeria de embeddings autorizados (funcionários ATIVOS com
    biometria ATIVA), descriptografando em memória apenas para o matching.
    """
    rows = await session.execute(
        select(Employee.employee_code, EmployeeBiometric.embedding_encrypted, EmployeeBiometric.embedding_dim)
        .join(EmployeeBiometric, EmployeeBiometric.employee_id == Employee.id)
        .where(
            Employee.status == EmployeeStatus.ACTIVE.value,
            Employee.is_deleted.is_(False),
            EmployeeBiometric.is_active.is_(True),
            Employee.biometric_status == BiometricStatus.ENROLLED.value,
        )
    )
    gallery: list[tuple[str, Sequence[float]]] = []
    for code, blob, dim in rows.all():
        try:
            gallery.append((code, decrypt_embedding(blob, dim)))
        except (InvalidToken, ValueError):
            # Modelo guardado com outra chave (ex.: a chave mudou) ou corrompido. Esse cadastro fica sem
            # reconhecimento até ser refeito, mas NÃO derruba o reconhecimento das demais pessoas.
            logger.warning("Modelo facial ilegível para %s; refazer o cadastro biométrico.", code)
    return gallery


async def run_match(
    session: AsyncSession,
    camera_id: str,
    frame: dict,
    recognition: FaceRecognitionService,
    actor: Principal,
    person_track_id: Optional[str] = None,
) -> tuple[FaceRecognitionEvent, IdentificationResult]:
    started = time.perf_counter()
    gallery = await load_gallery(session)
    result = recognition.identify(frame, gallery)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    metrics.record(result.status, elapsed_ms)

    event = FaceRecognitionEvent(
        camera_id=camera_id,
        person_track_id=person_track_id,
        employee_code=result.employee_code,
        status=result.status.value,
        quality_score=result.quality_score,
        similarity_score=result.similarity_score,
        confidence_score=result.confidence_score,
        runner_up_code=result.runner_up.employee_code if result.runner_up else None,
        runner_up_similarity=result.runner_up.similarity if result.runner_up else None,
        model_version=result.model_version,
        requires_review=result.requires_review,
        processing_ms=elapsed_ms,
    )
    session.add(event)

    # Auditoria: registra a tentativa e o acesso à galeria (metadados, sem embeddings).
    action = (
        AuditAction.RECOGNITION_AMBIGUOUS
        if result.status == RecognitionStatus.AMBIGUOUS
        else AuditAction.RECOGNITION_ATTEMPT
    )
    await record_audit(
        session,
        action,
        actor=actor.subject,
        actor_role=actor.role.value,
        resource_type="recognition_event",
        resource_id=camera_id,
        details={
            "status": result.status.value,
            "gallery_size": len(gallery),
            "confidence": result.confidence_score,
        },
    )
    await session.commit()
    await session.refresh(event)
    return event, result

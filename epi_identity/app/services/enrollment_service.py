from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import utcnow
from app.enums import AuditAction, BiometricStatus
from app.models import Employee, EmployeeBiometric
from app.recognition import FaceRecognitionService
from app.security.auth import Principal
from app.security.crypto import encrypt_embedding
from app.services.audit_service import record_audit


class ConsentRequiredError(Exception):
    pass


async def enroll_biometric(
    session: AsyncSession,
    employee: Employee,
    frame: dict,
    consent: bool,
    recognition: FaceRecognitionService,
    actor: Principal,
) -> EmployeeBiometric:
    """
    Gera e armazena o template biométrico protegido.
    Requer consentimento explícito (LGPD). Levanta QualityTooLowError se o
    rosto não passar no gate de qualidade.
    """
    if not (consent or employee.biometric_consent):
        raise ConsentRequiredError("Consentimento biométrico obrigatório (LGPD).")

    embedding = recognition.generate_enrollment_embedding(frame)  # pode levantar QualityTooLowError

    # Desativa templates anteriores (mantém histórico, marca novo como ativo).
    await session.execute(
        update(EmployeeBiometric)
        .where(EmployeeBiometric.employee_id == employee.id)
        .values(is_active=False)
    )

    biometric = EmployeeBiometric(
        employee_id=employee.id,
        embedding_encrypted=encrypt_embedding(embedding.vector),
        embedding_dim=len(embedding.vector),
        model_version=embedding.model_version,
        quality_score=embedding.quality_score,
        is_active=True,
        enrolled_by=actor.subject,
    )
    session.add(biometric)

    employee.biometric_status = BiometricStatus.ENROLLED.value
    if consent and not employee.biometric_consent:
        employee.biometric_consent = True
        employee.biometric_consent_at = utcnow()

    await record_audit(
        session,
        AuditAction.BIOMETRIC_ENROLL,
        actor=actor.subject,
        actor_role=actor.role.value,
        resource_type="employee_biometric",
        resource_id=employee.employee_code,
        details={"model_version": embedding.model_version, "quality": embedding.quality_score},
    )
    await session.commit()
    await session.refresh(biometric)
    return biometric


async def get_active_biometric(session: AsyncSession, employee_id: str) -> EmployeeBiometric | None:
    return await session.scalar(
        select(EmployeeBiometric).where(
            EmployeeBiometric.employee_id == employee_id,
            EmployeeBiometric.is_active.is_(True),
        )
    )


async def revoke_biometric(session: AsyncSession, employee: Employee, actor: Principal) -> int:
    """
    Apaga o modelo facial do funcionário (direito de apagar, LGPD) e retira o consentimento.
    Remove DE FATO os templates criptografados (não só desativa). Os eventos de reconhecimento já gravados
    guardam só metadados (código, status, notas) e continuam para auditoria. Idempotente.
    """
    result = await session.execute(delete(EmployeeBiometric).where(EmployeeBiometric.employee_id == employee.id))
    removed = int(result.rowcount or 0)
    employee.biometric_status = BiometricStatus.REVOKED.value
    employee.biometric_consent = False
    employee.biometric_consent_at = None
    await record_audit(
        session,
        AuditAction.BIOMETRIC_REVOKE,
        actor=actor.subject,
        actor_role=actor.role.value,
        resource_type="employee_biometric",
        resource_id=employee.employee_code,
        details={"deleted_templates": removed},
    )
    await session.commit()
    return removed

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_recognition_service, require_permission
from app.database import get_session
from app.enums import BiometricStatus
from app.recognition import FaceRecognitionService
from app.recognition.service import QualityTooLowError
from app.schemas.employee import (
    BiometricEnrollRequest,
    BiometricStatusOut,
)
from app.security.auth import Principal
from app.security.rbac import Permission
from app.services import employee_service, enrollment_service

router = APIRouter(prefix="/employees", tags=["biometrics"])


@router.post("/{employee_id}/biometric-enrollment", response_model=BiometricStatusOut)
async def enroll(
    employee_id: str,
    body: BiometricEnrollRequest,
    session: AsyncSession = Depends(get_session),
    recognition: FaceRecognitionService = Depends(get_recognition_service),
    actor: Principal = Depends(require_permission(Permission.BIOMETRIC_ENROLL)),
):
    try:
        employee = await employee_service.get_employee(session, employee_id)
    except employee_service.EmployeeNotFound:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

    try:
        biometric = await enrollment_service.enroll_biometric(
            session, employee, body.frame, body.consent, recognition, actor
        )
    except enrollment_service.ConsentRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_412_PRECONDITION_FAILED, detail=str(exc))
    except QualityTooLowError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "IDENTIFICATION_UNAVAILABLE", "reasons": exc.reasons},
        )

    return BiometricStatusOut(
        employee_code=employee.employee_code,
        biometric_status=BiometricStatus(employee.biometric_status),
        model_version=biometric.model_version,
        quality_score=biometric.quality_score,
        enrolled_at=biometric.created_at,
    )


@router.get("/{employee_id}/biometric-status", response_model=BiometricStatusOut)
async def biometric_status(
    employee_id: str,
    session: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_permission(Permission.BIOMETRIC_READ)),
):
    try:
        employee = await employee_service.get_employee(session, employee_id)
    except employee_service.EmployeeNotFound:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

    biometric = await enrollment_service.get_active_biometric(session, employee.id)
    return BiometricStatusOut(
        employee_code=employee.employee_code,
        biometric_status=BiometricStatus(employee.biometric_status),
        model_version=biometric.model_version if biometric else None,
        quality_score=biometric.quality_score if biometric else None,
        enrolled_at=biometric.created_at if biometric else None,
    )

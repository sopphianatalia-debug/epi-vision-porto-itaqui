from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import BiometricStatus, EmployeeStatus


class EmployeeCreate(BaseModel):
    registration: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    sector: str
    role_title: str


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    sector: Optional[str] = None
    role_title: Optional[str] = None
    status: Optional[EmployeeStatus] = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    employee_code: str
    registration: str
    name: str
    sector: str
    role_title: str
    status: str
    biometric_status: str
    created_at: datetime
    updated_at: datetime


class BiometricEnrollRequest(BaseModel):
    """
    Frame de captura. No provider mock é o dict de cena; com um provider real,
    seria a imagem (base64) — decodificada antes de chegar ao provider.
    """

    frame: dict
    consent: bool = Field(description="Consentimento explícito do titular (LGPD).")


class BiometricStatusOut(BaseModel):
    employee_code: str
    biometric_status: BiometricStatus
    model_version: Optional[str] = None
    quality_score: Optional[float] = None
    enrolled_at: Optional[datetime] = None

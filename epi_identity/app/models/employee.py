from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import BiometricStatus, EmployeeStatus


class Employee(Base):
    """
    Cadastro do funcionário.

    Regra: o nome NUNCA é identificador. A chave pública é `employee_code`
    (ex.: FUNC-000234); a PK interna é um UUID (herdado de Base).
    """

    __tablename__ = "employees"

    employee_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    registration: Mapped[str] = mapped_column(String(50), index=True)  # matrícula
    name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str] = mapped_column(String(100))
    role_title: Mapped[str] = mapped_column(String(100))  # cargo

    status: Mapped[str] = mapped_column(String(20), default=EmployeeStatus.ACTIVE.value)
    biometric_status: Mapped[str] = mapped_column(
        String(20), default=BiometricStatus.NOT_ENROLLED.value
    )

    # Consentimento explícito para uso de biometria (LGPD, base legal).
    biometric_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    biometric_consent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    biometrics = relationship(
        "EmployeeBiometric", back_populates="employee", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_employee_status_active", "status", "is_deleted"),)

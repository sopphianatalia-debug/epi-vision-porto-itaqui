from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmployeeBiometric(Base):
    """
    Template biométrico protegido.

    O embedding é armazenado SEMPRE criptografado (`embedding_encrypted`).
    Nenhuma imagem facial bruta é persistida por padrão (ver config).
    A comparação vetorial ocorre em memória, no serviço de reconhecimento,
    após descriptografia controlada e auditada.
    """

    __tablename__ = "employee_biometrics"

    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), index=True
    )

    # Embedding criptografado (Fernet/AES). Nunca em texto claro.
    embedding_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    embedding_dim: Mapped[int] = mapped_column(Integer)

    # Versão do modelo que gerou o embedding — essencial para migração de modelo.
    model_version: Mapped[str] = mapped_column(String(50), index=True)

    quality_score: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    enrolled_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    employee = relationship("Employee", back_populates="biometrics")

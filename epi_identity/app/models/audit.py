from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """
    Trilha de auditoria imutável (append-only por convenção de serviço).
    Responde a QUEM fez, O QUÊ, QUANDO e sobre QUAL recurso.
    """

    __tablename__ = "audit_logs"

    action: Mapped[str] = mapped_column(String(50), index=True)  # AuditAction
    actor: Mapped[str] = mapped_column(String(100), index=True)  # usuário/serviço
    actor_role: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Detalhes sem dados biométricos brutos (apenas metadados).
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

"""
Associação track -> identidade, com TTL e reidentificação.

Mantém a identidade anexada ao person_track_id mesmo se o rosto ficar
temporariamente oculto (dentro do identity_ttl). Solicita revalidação quando
a associação envelhece e encerra a identidade se expirar.

Este componente NÃO decide identidade (isso é do FaceRecognitionService);
apenas guarda e expira a decisão já tomada, mantendo a separação explícita
entre person_track_id e employee_code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class Identity:
    employee_code: str
    confidence: float
    assigned_at: datetime
    last_validated_at: datetime


class IdentityManager:
    def __init__(self, identity_ttl_seconds: int = 30, revalidate_after_seconds: int = 10) -> None:
        self.identity_ttl = timedelta(seconds=identity_ttl_seconds)
        self.revalidate_after = timedelta(seconds=revalidate_after_seconds)
        self._identities: dict[str, Identity] = {}

    def assign(self, track_code: str, employee_code: str, confidence: float, now: datetime) -> None:
        self._identities[track_code] = Identity(
            employee_code=employee_code,
            confidence=confidence,
            assigned_at=now,
            last_validated_at=now,
        )

    def touch(self, track_code: str, now: datetime, confidence: Optional[float] = None) -> None:
        """Renova a validação da identidade (novo reconhecimento confirmou o mesmo funcionário)."""
        ident = self._identities.get(track_code)
        if ident is not None:
            ident.last_validated_at = now
            if confidence is not None:
                ident.confidence = confidence

    def get_identity(self, track_code: str, now: datetime) -> Optional[Identity]:
        ident = self._identities.get(track_code)
        if ident is None:
            return None
        if now - ident.last_validated_at > self.identity_ttl:
            # Expirou: perde a identidade (mas o track pode continuar como desconhecido).
            del self._identities[track_code]
            return None
        return ident

    def should_revalidate(self, track_code: str, now: datetime) -> bool:
        ident = self._identities.get(track_code)
        if ident is None:
            return True
        return now - ident.last_validated_at > self.revalidate_after

    def release(self, track_code: str) -> None:
        self._identities.pop(track_code, None)

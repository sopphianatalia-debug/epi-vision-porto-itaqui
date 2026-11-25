"""
IdentityCache — Fase 3.7, seção 19.

Evita chamar `POST /recognition/match` em todo frame para a mesma pessoa
sendo rastreada pela câmera. A chave é (camera_id, person_track_id) — nunca
employee_id, porque antes da identificação nem sabemos quem é a pessoa.

Guarda apenas o resultado da identificação (status, employee_id ou None,
confidence) — nenhum dado biométrico, nenhuma imagem, nenhum embedding.

Clock injetável (mesmo padrão usado em epi_fusion/epi_rules/epi_incident)
para permitir testar expiração sem `time.sleep`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class CachedIdentity:
    employee_id: Optional[str]
    identity_status: str
    identity_confidence: float
    cached_at: datetime
    expires_at: datetime

    def to_identity_fields(self) -> dict:
        return {
            "employee_id": self.employee_id,
            "identity_status": self.identity_status,
            "identity_confidence": self.identity_confidence,
        }


class IdentityCache:
    def __init__(self, ttl_seconds: float = 2.0, clock: Callable[[], datetime] = _utcnow) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._clock = clock
        self._store: dict[tuple[str, str], CachedIdentity] = {}

    def get(self, camera_id: str, person_track_id: str) -> Optional[CachedIdentity]:
        entry = self._store.get((camera_id, person_track_id))
        if entry is None:
            return None
        if self._clock() >= entry.expires_at:
            del self._store[(camera_id, person_track_id)]
            return None
        return entry

    def put(self, camera_id: str, person_track_id: str, identity_fields: dict,
            ttl_seconds: Optional[float] = None) -> CachedIdentity:
        now = self._clock()
        ttl = self._ttl if ttl_seconds is None else timedelta(seconds=ttl_seconds)
        entry = CachedIdentity(
            employee_id=identity_fields["employee_id"],
            identity_status=identity_fields["identity_status"],
            identity_confidence=identity_fields["identity_confidence"],
            cached_at=now,
            expires_at=now + ttl,
        )
        self._store[(camera_id, person_track_id)] = entry
        return entry

    def invalidate(self, camera_id: str, person_track_id: str) -> None:
        self._store.pop((camera_id, person_track_id), None)

    def size(self) -> int:
        return len(self._store)

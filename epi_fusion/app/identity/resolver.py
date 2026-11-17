"""
Resolução de identidade.

IdentityResolver é o ponto de extensão para a FASE 3.2. Nesta fase existe apenas
o EmployeeIdIdentityResolver: usa o employee_id que já veio na observação, e SÓ
aceita como chave se a identidade for MATCHED, com confiança suficiente e o
funcionário for válido/ativo. Caso contrário, NÃO atribui (conservadorismo).

Futuros resolvers (NÃO implementados aqui): SpatialIdentityResolver,
ReIdentificationResolver, MultiCameraIdentityResolver.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Protocol

from app.domain.enums import JOINABLE_IDENTITY, IdentityStatus
from app.domain.models import Observation


@dataclass(frozen=True)
class IdentityResolution:
    employee_id: Optional[str]
    identity_status: IdentityStatus
    reason: str = ""

    @property
    def is_joinable(self) -> bool:
        return self.employee_id is not None and self.identity_status in JOINABLE_IDENTITY


class EmployeeDirectory(Protocol):
    """Porta para validar existência/atividade de um funcionário."""

    def is_valid(self, employee_id: str) -> bool: ...
    def is_active(self, employee_id: str) -> bool: ...


class InMemoryEmployeeDirectory:
    """Diretório simples. Em produção, integrar ao cadastro do Módulo 1."""

    def __init__(self, active: set[str] | None = None, inactive: set[str] | None = None) -> None:
        self._active = active or set()
        self._inactive = inactive or set()

    def add(self, employee_id: str, active: bool = True) -> None:
        (self._active if active else self._inactive).add(employee_id)

    def is_valid(self, employee_id: str) -> bool:
        return employee_id in self._active or employee_id in self._inactive

    def is_active(self, employee_id: str) -> bool:
        return employee_id in self._active


class PermissiveEmployeeDirectory:
    """Aceita qualquer employee_id bem formado (para dev/testes sem cadastro)."""

    def is_valid(self, employee_id: str) -> bool:
        return bool(employee_id) and employee_id.startswith("FUNC-")

    def is_active(self, employee_id: str) -> bool:
        return self.is_valid(employee_id)


class IdentityResolver(ABC):
    @abstractmethod
    def resolve(self, observation: Observation) -> IdentityResolution: ...


class EmployeeIdIdentityResolver(IdentityResolver):
    def __init__(self, directory: EmployeeDirectory, confidence_threshold: float) -> None:
        self._dir = directory
        self._threshold = confidence_threshold

    def resolve(self, obs: Observation) -> IdentityResolution:
        # Só MATCHED pode virar chave de junção.
        if obs.identity_status not in JOINABLE_IDENTITY:
            return IdentityResolution(None, obs.identity_status, "not_matched")

        if not obs.employee_id:
            return IdentityResolution(None, IdentityStatus.NOT_IDENTIFIED, "no_employee_id")

        if obs.identity_confidence < self._threshold:
            return IdentityResolution(None, IdentityStatus.LOW_CONFIDENCE, "identity_confidence_below_threshold")

        if not self._dir.is_valid(obs.employee_id):
            return IdentityResolution(None, IdentityStatus.NOT_IDENTIFIED, "invalid_employee_id")

        if not self._dir.is_active(obs.employee_id):
            return IdentityResolution(None, IdentityStatus.NOT_IDENTIFIED, "inactive_employee_id")

        return IdentityResolution(obs.employee_id, IdentityStatus.MATCHED, "ok")


def build_identity_resolver(name: str, directory: EmployeeDirectory, threshold: float) -> IdentityResolver:
    if name == "employee_id":
        return EmployeeIdIdentityResolver(directory, threshold)
    # Reservado para a FASE 3.2:
    raise ValueError(f"IdentityResolver desconhecido nesta fase: {name!r}")

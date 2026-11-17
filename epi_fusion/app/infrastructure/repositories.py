"""
Repositórios em memória com expiração por janela temporal.

As interfaces isolam a persistência: trocar por Postgres/Redis depois não afeta
o FusionService. As observações originais são mantidas conforme a janela; o
estado consolidado é materializado/cacheado.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta

from app.domain.models import (
    AnonymousObservation,
    CameraVisibilityProfile,
    EmployeeSafetyState,
    FusionConflict,
    Observation,
)


class ObservationRepository:
    """Guarda observações identificadas por funcionário, com poda por janela."""

    def __init__(self, retain_per_key: int = 200) -> None:
        self._by_employee: dict[str, deque[Observation]] = defaultdict(lambda: deque(maxlen=retain_per_key))
        self._by_camera: dict[str, deque[Observation]] = defaultdict(lambda: deque(maxlen=retain_per_key))

    def add(self, obs: Observation) -> None:
        assert obs.employee_id is not None
        self._by_employee[obs.employee_id].append(obs)
        self._by_camera[obs.camera_id].append(obs)

    def recent_for_employee(self, employee_id: str, since: datetime) -> list[Observation]:
        return [o for o in self._by_employee.get(employee_id, ()) if o.timestamp >= since]

    def latest_per_camera(self, employee_id: str, since: datetime) -> dict[str, Observation]:
        latest: dict[str, Observation] = {}
        for o in self.recent_for_employee(employee_id, since):
            cur = latest.get(o.camera_id)
            if cur is None or o.timestamp >= cur.timestamp:
                latest[o.camera_id] = o
        return latest

    def for_camera(self, camera_id: str, limit: int = 50) -> list[Observation]:
        return list(self._by_camera.get(camera_id, ()))[-limit:][::-1]

    def employees(self) -> list[str]:
        return list(self._by_employee.keys())


class StateRepository:
    def __init__(self) -> None:
        self._states: dict[str, EmployeeSafetyState] = {}

    def put(self, state: EmployeeSafetyState) -> None:
        self._states[state.employee_id] = state

    def get(self, employee_id: str) -> EmployeeSafetyState | None:
        return self._states.get(employee_id)

    def all(self) -> list[EmployeeSafetyState]:
        return list(self._states.values())

    def remove(self, employee_id: str) -> None:
        self._states.pop(employee_id, None)


class AnonymousRepository:
    def __init__(self, maxlen: int = 500) -> None:
        self._obs: deque[AnonymousObservation] = deque(maxlen=maxlen)

    def add(self, obs: AnonymousObservation) -> None:
        self._obs.append(obs)

    def recent(self, limit: int = 50) -> list[AnonymousObservation]:
        return list(self._obs)[-limit:][::-1]

    @property
    def count(self) -> int:
        return len(self._obs)


class ConflictRepository:
    def __init__(self, maxlen: int = 500) -> None:
        self._conflicts: deque[FusionConflict] = deque(maxlen=maxlen)

    def add(self, conflict: FusionConflict) -> None:
        self._conflicts.append(conflict)

    def recent(self, limit: int = 50) -> list[FusionConflict]:
        return list(self._conflicts)[-limit:][::-1]

    @property
    def count(self) -> int:
        return len(self._conflicts)


class VisibilityProfileRepository:
    def __init__(self) -> None:
        self._profiles: dict[str, CameraVisibilityProfile] = {}

    def put(self, profile: CameraVisibilityProfile) -> None:
        self._profiles[profile.camera_id] = profile

    def get(self, camera_id: str) -> CameraVisibilityProfile | None:
        return self._profiles.get(camera_id)

    def all(self) -> list[CameraVisibilityProfile]:
        return list(self._profiles.values())

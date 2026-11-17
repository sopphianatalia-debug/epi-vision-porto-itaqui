"""
Metricas do epi_tracker - secao 32 do pedido.

Usa RLock (nao Lock) de proposito: ja descobrimos na Fase 3.6 que um
metodo que chama outro metodo do mesmo objeto enquanto segura o cadeado
(ex.: snapshot() usando uma property que tambem trava) causa deadlock
com Lock comum. RLock evita essa classe inteira de bug desde o primeiro
dia neste modulo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock


@dataclass
class TrackerMetrics:
    employees_checked: int = 0
    safety_checks_total: int = 0
    compliant_checks: int = 0
    non_compliant_checks: int = 0
    indeterminate_checks: int = 0

    trackers_total: int = 0
    trackers_active: int = 0
    trackers_offline: int = 0
    trackers_low_battery: int = 0

    tracker_observations_total: int = 0
    location_updates: int = 0
    location_expirations: int = 0

    observations_by_area: dict = field(default_factory=dict)
    employees_by_area: dict = field(default_factory=dict)
    ppe_by_area: dict = field(default_factory=dict)

    _lock: RLock = field(default_factory=RLock, repr=False)

    def record_safety_check(self, status: str) -> None:
        with self._lock:
            self.safety_checks_total += 1
            if status == "COMPLIANT":
                self.compliant_checks += 1
            elif status == "NON_COMPLIANT":
                self.non_compliant_checks += 1
            elif status == "INDETERMINATE":
                self.indeterminate_checks += 1

    def record_tracker_registered(self) -> None:
        with self._lock:
            self.trackers_total += 1
            self.trackers_active += 1

    def record_status_change(self, old_status: str, new_status: str) -> None:
        with self._lock:
            self._decrement_status(old_status)
            self._increment_status(new_status)

    def _increment_status(self, status: str) -> None:
        if status == "ACTIVE":
            self.trackers_active += 1
        elif status == "OFFLINE":
            self.trackers_offline += 1
        elif status == "LOW_BATTERY":
            self.trackers_low_battery += 1

    def _decrement_status(self, status: str) -> None:
        if status == "ACTIVE":
            self.trackers_active = max(0, self.trackers_active - 1)
        elif status == "OFFLINE":
            self.trackers_offline = max(0, self.trackers_offline - 1)
        elif status == "LOW_BATTERY":
            self.trackers_low_battery = max(0, self.trackers_low_battery - 1)

    def record_observation(self, area_id: str) -> None:
        with self._lock:
            self.tracker_observations_total += 1
            self.location_updates += 1
            self.observations_by_area[area_id] = self.observations_by_area.get(area_id, 0) + 1

    def record_expiration(self) -> None:
        with self._lock:
            self.location_expirations += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "employees_checked": self.employees_checked,
                "safety_checks_total": self.safety_checks_total,
                "compliant_checks": self.compliant_checks,
                "non_compliant_checks": self.non_compliant_checks,
                "indeterminate_checks": self.indeterminate_checks,
                "trackers_total": self.trackers_total,
                "trackers_active": self.trackers_active,
                "trackers_offline": self.trackers_offline,
                "trackers_low_battery": self.trackers_low_battery,
                "tracker_observations_total": self.tracker_observations_total,
                "location_updates": self.location_updates,
                "location_expirations": self.location_expirations,
                "observations_by_area": dict(self.observations_by_area),
            }

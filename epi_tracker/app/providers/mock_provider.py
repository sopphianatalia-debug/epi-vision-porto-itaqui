"""
MockTrackerProvider - secao 25 do pedido.

Permite simular, via chamadas explicitas de teste/demo (nao ha hardware
real nesta fase):
- movimentacao entre areas (TRACKER-001 -> PATIO-01 -> PATIO-02 -> MANUTENCAO);
- LOW_BATTERY;
- OFFLINE;
- LOCATION_EXPIRED (via TTL calculado pelo servico, nao aqui);
- UNKNOWN_TRACKER (tracker nunca registrado no provider).

O provider NUNCA decide conformidade nem TTL - so guarda "a ultima leitura
simulada" por tracker, exatamente como um leitor de RFID/BLE real faria.
"""
from __future__ import annotations

from typing import Optional


class MockTrackerProvider:
    def __init__(self) -> None:
        # tracker_id -> {"area_id", "signal_strength", "battery_level", "offline"}
        self._state: dict[str, dict] = {}

    def simulate_location(self, tracker_id: str, area_id: str, signal_strength: float = 0.9) -> None:
        """Simula uma nova leitura de localizacao (POST /demo/location)."""
        entry = self._state.setdefault(tracker_id, {})
        entry["area_id"] = area_id
        entry["signal_strength"] = signal_strength
        entry["offline"] = False

    def simulate_low_battery(self, tracker_id: str, level: float = 0.05) -> None:
        entry = self._state.setdefault(tracker_id, {})
        entry["battery_level"] = level

    def simulate_battery_ok(self, tracker_id: str, level: float = 0.95) -> None:
        entry = self._state.setdefault(tracker_id, {})
        entry["battery_level"] = level

    def simulate_offline(self, tracker_id: str) -> None:
        entry = self._state.setdefault(tracker_id, {})
        entry["offline"] = True

    def simulate_online(self, tracker_id: str) -> None:
        entry = self._state.setdefault(tracker_id, {})
        entry["offline"] = False

    def read_location(self, tracker_id: str) -> Optional[dict]:
        entry = self._state.get(tracker_id)
        if entry is None:
            return None  # UNKNOWN_TRACKER - provider nunca ouviu falar desse tracker
        if entry.get("offline"):
            return {"offline": True, "area_id": entry.get("area_id"),
                     "battery_level": entry.get("battery_level")}
        return {
            "offline": False,
            "area_id": entry.get("area_id"),
            "signal_strength": entry.get("signal_strength"),
            "battery_level": entry.get("battery_level"),
        }

"""Interface do provider de localizacao - permite trocar MOCK por
BLE/RFID/UWB reais no futuro (secao 34: arquitetura agnostica de tecnologia)."""
from __future__ import annotations

from typing import Optional, Protocol


class LocationProvider(Protocol):
    def read_location(self, tracker_id: str) -> Optional[dict]:
        """Retorna um dict com pelo menos {"area_id": str, "signal_strength":
        float|None, "battery_level": float|None} ou None se o tracker for
        desconhecido do provider. Nunca decide TTL/expiracao - isso e
        responsabilidade do TrackerService (a evidencia bruta e uma coisa,
        a interpretacao dela com o relogio e outra)."""
        ...

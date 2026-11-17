"""
EventBus injetavel - secao 28 do pedido.

Eventos:
EMPLOYEE_ENTERED_AREA, EMPLOYEE_EXITED_AREA, SAFETY_CHECK_STARTED,
SAFETY_CHECK_COMPLETED, TRACKER_DETECTED, TRACKER_LOCATION_UPDATED,
TRACKER_ENTERED_AREA, TRACKER_EXITED_AREA, TRACKER_OFFLINE,
TRACKER_LOW_BATTERY, TRACKER_LOCATION_EXPIRED,
POSSIBLE_PPE_LOCATION_INCONSISTENCY
"""
from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    EMPLOYEE_ENTERED_AREA = "EMPLOYEE_ENTERED_AREA"
    EMPLOYEE_EXITED_AREA = "EMPLOYEE_EXITED_AREA"
    SAFETY_CHECK_STARTED = "SAFETY_CHECK_STARTED"
    SAFETY_CHECK_COMPLETED = "SAFETY_CHECK_COMPLETED"
    TRACKER_DETECTED = "TRACKER_DETECTED"
    TRACKER_LOCATION_UPDATED = "TRACKER_LOCATION_UPDATED"
    TRACKER_ENTERED_AREA = "TRACKER_ENTERED_AREA"
    TRACKER_EXITED_AREA = "TRACKER_EXITED_AREA"
    TRACKER_OFFLINE = "TRACKER_OFFLINE"
    TRACKER_LOW_BATTERY = "TRACKER_LOW_BATTERY"
    TRACKER_LOCATION_EXPIRED = "TRACKER_LOCATION_EXPIRED"
    POSSIBLE_PPE_LOCATION_INCONSISTENCY = "POSSIBLE_PPE_LOCATION_INCONSISTENCY"


class InMemoryEventBus:
    """Mesmo padrao simples de pub/sub em memoria usado em
    epi_fusion/epi_incident - sem fila persistente, sem broker externo."""

    def __init__(self) -> None:
        self._history = []

    def publish(self, event_type: EventType, payload: dict) -> None:
        self._history.append((event_type, payload))

    def history(self):
        return list(self._history)

    def count(self, event_type: EventType) -> int:
        return sum(1 for et, _ in self._history if et == event_type)

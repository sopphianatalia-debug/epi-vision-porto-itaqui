"""Event Bus — abstração para o futuro Incident Service consumir."""
from __future__ import annotations

from collections import deque
from typing import Callable

from app.domain.enums import EventType

Handler = Callable[[EventType, dict], None]


class EventBus:
    def publish(self, event_type: EventType, payload: dict) -> None:  # pragma: no cover
        raise NotImplementedError

    def subscribe(self, handler: Handler) -> None:  # pragma: no cover
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    def __init__(self, history: int = 500) -> None:
        self._handlers: list[Handler] = []
        self._history: deque[dict] = deque(maxlen=history)

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    def publish(self, event_type: EventType, payload: dict) -> None:
        self._history.append({"type": event_type.value, **payload})
        for h in self._handlers:
            h(event_type, payload)

    def recent(self, limit: int = 100) -> list[dict]:
        return list(self._history)[-limit:][::-1]

"""
WebSocket de eventos de incidente: ws://.../api/v1/ws/incidents

Ao conectar, recebe {"type":"SNAPSHOT","incidents":[...abertos...]}; depois recebe cada evento do
barramento (INCIDENT_CREATED / UPDATED / RESOLVED / REVIEWED) como {"type": "...", ...payload}.
É só difusão: não decide nada e não altera incidentes. O cliente deve manter uma consulta REST
periódica como reserva (a conexão pode cair).
"""
from __future__ import annotations

import asyncio
import threading
from typing import Optional

from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import get_hub, get_service
from app.auth import verify_token
from app.config import get_settings

router = APIRouter()


class WsHub:
    """Ponte entre o EventBus (síncrono, chamado de threads) e os clientes WebSocket (asyncio)."""

    def __init__(self) -> None:
        self._clients: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> tuple[asyncio.AbstractEventLoop, asyncio.Queue]:
        item = (asyncio.get_running_loop(), asyncio.Queue(maxsize=200))
        with self._lock:
            self._clients.add(item)
        return item

    def unsubscribe(self, item) -> None:
        with self._lock:
            self._clients.discard(item)

    @property
    def clients(self) -> int:
        with self._lock:
            return len(self._clients)

    def on_event(self, event_type, payload: dict) -> None:
        """Handler do EventBus. Nunca levanta erro (não pode derrubar o serviço)."""
        message = {"type": getattr(event_type, "value", str(event_type)), **payload}
        with self._lock:
            targets = list(self._clients)
        for loop, queue in targets:
            try:
                loop.call_soon_threadsafe(self._offer, queue, message)
            except RuntimeError:  # loop fechado
                pass

    @staticmethod
    def _offer(queue: asyncio.Queue, message: dict) -> None:
        if queue.full():          # cliente lento: descarta o mais antigo, mantém o fluxo
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(message)


@router.websocket("/ws/incidents")
async def incidents_ws(ws: WebSocket, token: Optional[str] = None):
    """Com INC_AUTH_MODE=required, exige ?token=<JWT do epi_auth> (o navegador não manda cabeçalho no WebSocket)."""
    if get_settings().auth_mode == "required" and (not token or verify_token(token) is None):
        await ws.close(code=4401)
        return
    svc = get_service()
    hub = get_hub()
    await ws.accept()
    sub = hub.subscribe()
    try:
        now = svc.now()
        await ws.send_json({"type": "SNAPSHOT",
                            "incidents": [i.to_dict(now) for i in svc.list(status="OPEN")]})
        while True:
            message = await sub[1].get()
            await ws.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(sub)

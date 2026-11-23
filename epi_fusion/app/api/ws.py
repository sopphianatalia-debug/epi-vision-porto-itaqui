"""
WebSocket de estado das câmeras: ws://.../api/v1/fusion/ws/cameras

Ao conectar envia {"type":"SNAPSHOT","cameras":[{camera_id,status,...}]}. Depois, só quando o
estado de uma câmera MUDA (ONLINE <-> OFFLINE, ou câmera nova), envia
{"type":"CAMERA_STATUS_CHANGED","camera_id","status","previous_status","last_observation_at"}.

Descreve apenas se a câmera está enviando dados. Não decide conformidade, não abre incidente e
silêncio de câmera nunca é tratado como violação.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.observability import metrics

router = APIRouter()


def diff_status(previous: dict[str, str], rows: list[dict]) -> list[dict]:
    """Eventos para as câmeras cujo estado mudou desde `previous` (camera_id -> status)."""
    events = []
    for r in rows:
        before = previous.get(r["camera_id"])
        if before != r["status"]:
            events.append({"type": "CAMERA_STATUS_CHANGED", "camera_id": r["camera_id"],
                           "status": r["status"], "previous_status": before,
                           "last_observation_at": r["last_observation_at"]})
    return events


@router.get("/fusion/cameras/status", tags=["observability"])
def cameras_status():
    return {"cameras": metrics.camera_status(get_settings().camera_stale_seconds)}


@router.websocket("/fusion/ws/cameras")
async def cameras_ws(ws: WebSocket):
    await ws.accept()
    settings = get_settings()
    try:
        rows = metrics.camera_status(settings.camera_stale_seconds)
        await ws.send_json({"type": "SNAPSHOT", "cameras": rows})
        known = {r["camera_id"]: r["status"] for r in rows}
        while True:
            await asyncio.sleep(settings.ws_poll_seconds)
            rows = metrics.camera_status(settings.camera_stale_seconds)
            for ev in diff_status(known, rows):
                await ws.send_json(ev)
            known = {r["camera_id"]: r["status"] for r in rows}
    except WebSocketDisconnect:
        pass

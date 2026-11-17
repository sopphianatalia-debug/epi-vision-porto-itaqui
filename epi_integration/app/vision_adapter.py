"""Converte detecções entre o formato do grupo (FastAPI deles) e o nosso.

Grupo : {"class_id": 0, "class_name": "person", "confidence": 0.91,
         "bbox": {"x1":..,"y1":..,"x2":..,"y2":..}}
Nosso : {"type": "person", "confidence": 0.91, "bbox": [x1, y1, x2, y2]}

Só traduz formato; não decide nada. Classe desconhecida é descartada (em vez
de adivinhada), igual ao mapa de classes do epi_ppe.
"""
from __future__ import annotations

from typing import Iterable

_GROUP_TO_OURS = {
    "person": "person",
    "helmet": "helmet", "hardhat": "helmet",
    "vest": "vest", "safety vest": "vest",
}


def group_to_ours(detections: Iterable[dict]) -> list[dict]:
    out = []
    for d in detections:
        kind = _GROUP_TO_OURS.get(str(d.get("class_name", "")).strip().lower())
        bbox = d.get("bbox") or {}
        if kind is None or not all(k in bbox for k in ("x1", "y1", "x2", "y2")):
            continue
        out.append({
            "type": kind,
            "confidence": float(d["confidence"]),
            "bbox": [float(bbox["x1"]), float(bbox["y1"]), float(bbox["x2"]), float(bbox["y2"])],
        })
    return out


def ours_to_group(detections: Iterable[dict]) -> list[dict]:
    out = []
    for d in detections:
        b = d.get("bbox") or []
        if len(b) != 4:
            continue
        out.append({
            "class_name": d["type"],
            "confidence": float(d["confidence"]),
            "bbox": {"x1": b[0], "y1": b[1], "x2": b[2], "y2": b[3]},
        })
    return out

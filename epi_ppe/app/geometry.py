"""Funções geométricas compartilhadas."""
from __future__ import annotations

from app.types import BoundingBox


def intersection_area(a: BoundingBox, b: BoundingBox) -> float:
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)


def iou(a: BoundingBox, b: BoundingBox) -> float:
    inter = intersection_area(a, b)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def containment(inner: BoundingBox, outer: BoundingBox) -> float:
    """Fração da caixa `inner` que está contida em `outer` (0..1)."""
    if inner.area == 0:
        return 0.0
    return intersection_area(inner, outer) / inner.area

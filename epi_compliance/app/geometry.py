"""Funções geométricas (sem dependências externas)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def as_list(self) -> list[float]:
        return [self.x1, self.y1, self.x2, self.y2]


def intersection_area(a: BoundingBox, b: BoundingBox) -> float:
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    return max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)


def containment(inner: BoundingBox, outer: BoundingBox) -> float:
    """Fração de `inner` contida em `outer` (0..1)."""
    if inner.area == 0:
        return 0.0
    return intersection_area(inner, outer) / inner.area


def coverage(covering: BoundingBox, region: BoundingBox) -> float:
    """Fração de `region` coberta por `covering` (0..1)."""
    if region.area == 0:
        return 0.0
    return intersection_area(covering, region) / region.area


def center_inside(inner: BoundingBox, outer: BoundingBox) -> bool:
    cx, cy = inner.center
    return outer.x1 <= cx <= outer.x2 and outer.y1 <= cy <= outer.y2

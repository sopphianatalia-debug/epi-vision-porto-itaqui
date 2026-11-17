"""
Definição das regiões corporais a partir da caixa da pessoa.

Frações verticais/horizontais aproximadas (proporções antropométricas). Quando
houver pose real, estas caixas são substituídas pelos keypoints; sem pose, são
uma estimativa suficiente para gating de visibilidade e posicionamento.
"""
from __future__ import annotations

from app.enums import BodyRegion
from app.geometry import BoundingBox

# (frac_top, frac_bottom, frac_left, frac_right) dentro da caixa da pessoa.
REGION_FRACTIONS: dict[BodyRegion, tuple[float, float, float, float]] = {
    BodyRegion.HEAD: (0.00, 0.20, 0.20, 0.80),
    BodyRegion.EYES: (0.05, 0.16, 0.25, 0.75),
    BodyRegion.TORSO: (0.20, 0.55, 0.10, 0.90),
    BodyRegion.LEFT_HAND: (0.45, 0.75, 0.00, 0.35),
    BodyRegion.RIGHT_HAND: (0.45, 0.75, 0.65, 1.00),
    BodyRegion.LEGS: (0.55, 0.90, 0.20, 0.80),
    BodyRegion.FEET: (0.90, 1.00, 0.15, 0.85),
}


def region_bbox(person: BoundingBox, region: BodyRegion) -> BoundingBox:
    ft, fb, fl, fr = REGION_FRACTIONS[region]
    return BoundingBox(
        x1=person.x1 + fl * person.width,
        y1=person.y1 + ft * person.height,
        x2=person.x1 + fr * person.width,
        y2=person.y1 + fb * person.height,
    )

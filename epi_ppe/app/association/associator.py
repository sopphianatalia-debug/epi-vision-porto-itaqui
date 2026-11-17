"""
Associação pessoa ↔ EPI (seção 6 do spec).

Estimar a que pessoa um EPI pertence, combinando:
- contenção: fração do EPI dentro da caixa da pessoa;
- região corporal esperada: capacete no topo, botas embaixo, colete no torso...
- (implicitamente) distância, via a posição vertical relativa.

Cada EPI é atribuído à pessoa de maior score, desde que acima do limiar. Assim,
um capacete distante ([700,300,...]) não é associado a uma pessoa em [100,100,...].
"""
from __future__ import annotations

from app.enums import DetectionClass
from app.geometry import containment
from app.types import BoundingBox, Detection, PersonResult, PPEDetection

# Faixa vertical esperada do EPI dentro da pessoa (0 = topo da cabeça, 1 = pés).
EXPECTED_REGION: dict[DetectionClass, tuple[float, float]] = {
    DetectionClass.HELMET: (0.00, 0.30),
    DetectionClass.SAFETY_GLASSES: (0.00, 0.28),
    DetectionClass.EAR_PROTECTION: (0.00, 0.32),
    DetectionClass.SAFETY_VEST: (0.20, 0.70),
    DetectionClass.GLOVES: (0.30, 0.95),
    DetectionClass.SAFETY_BOOTS: (0.75, 1.00),
}


def _region_match(ppe_bbox: BoundingBox, person_bbox: BoundingBox, cls: DetectionClass) -> float:
    """1.0 se o centro do EPI cai na faixa vertical esperada; decai fora dela."""
    expected = EXPECTED_REGION.get(cls)
    if expected is None or person_bbox.height == 0:
        return 1.0
    cy = ppe_bbox.center[1]
    rel = (cy - person_bbox.y1) / person_bbox.height  # 0..1 dentro da pessoa
    low, high = expected
    if low <= rel <= high:
        return 1.0
    # Distância à faixa, normalizada; vira um decaimento suave (não zera bruscamente).
    dist = (low - rel) if rel < low else (rel - high)
    return max(0.0, 1.0 - dist / 0.35)


def association_score(
    ppe: Detection, person: Detection, containment_threshold: float
) -> float:
    """Score 0..1 de que o EPI pertence à pessoa. 0 se pouco contido."""
    cont = containment(ppe.bbox, person.bbox)
    if cont < containment_threshold:
        return 0.0
    region = _region_match(ppe.bbox, person.bbox, ppe.cls)
    return cont * region


class PersonPPEAssociator:
    def __init__(self, containment_threshold: float, score_threshold: float) -> None:
        self.containment_threshold = containment_threshold
        self.score_threshold = score_threshold

    def associate(
        self, persons: list[tuple[str, Detection]], ppes: list[Detection]
    ) -> list[PersonResult]:
        """
        `persons`: lista de (person_track_id, Detection da pessoa).
        Retorna um PersonResult por pessoa, com os EPIs atribuídos.
        Cada EPI vai para no máximo uma pessoa (a de maior score).
        """
        results = {
            tid: PersonResult(
                person_track_id=tid,
                person_bbox=det.bbox,
                person_confidence=det.confidence,
            )
            for tid, det in persons
        }

        for ppe in ppes:
            best_tid: str | None = None
            best_score = self.score_threshold
            for tid, person in persons:
                score = association_score(ppe, person, self.containment_threshold)
                if score >= best_score:
                    best_score = score
                    best_tid = tid
            if best_tid is not None:
                results[best_tid].ppe.append(
                    PPEDetection(
                        cls=ppe.cls,
                        confidence=ppe.confidence,
                        bbox=ppe.bbox,
                        association_score=best_score,
                    )
                )

        return list(results.values())

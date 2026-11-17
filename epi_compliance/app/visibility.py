"""
Análise de visibilidade — a regra mais importante do módulo.

Uma região corporal só pode ser avaliada se estiver de fato dentro do campo de
visão. Se a pessoa está cortada pela borda (ex.: câmera mostra só o torso) ou a
região cai fora do frame, marcamos NOT_VISIBLE — e o avaliador NUNCA conclui
"ausente" nesse caso (seções 6, 7 e 14 do spec).
"""
from __future__ import annotations

from app.enums import BodyRegion, Visibility
from app.geometry import BoundingBox
from app.pose import PoseProvider
from app.types import PersonObservation


class VisibilityAnalyzer:
    def __init__(self, pose: PoseProvider, edge_margin: float = 0.01) -> None:
        self._pose = pose
        self._edge_margin = edge_margin

    def analyze(self, obs: PersonObservation) -> dict[BodyRegion, Visibility]:
        # Override explícito (ex.: pose real informou o que enxergou).
        if obs.visible_regions:
            return {r: obs.visible_regions.get(r, Visibility.NOT_VISIBLE) for r in BodyRegion}

        regions = self._pose.regions(obs.person_bbox)
        mx = self._edge_margin * obs.frame_width
        my = self._edge_margin * obs.frame_height
        frame = BoundingBox(mx, my, obs.frame_width - mx, obs.frame_height - my)

        result: dict[BodyRegion, Visibility] = {}
        for region, box in regions.items():
            result[region] = (
                Visibility.VISIBLE if self._within(box, frame) else Visibility.NOT_VISIBLE
            )

        # Pessoa cortada pela borda: a região daquele lado não é confiável,
        # mesmo que a caixa recortada caiba no frame (ex.: câmera só do torso).
        p = obs.person_bbox
        if p.y2 >= obs.frame_height - my:      # cortada embaixo -> pés/pernas
            result[BodyRegion.FEET] = Visibility.NOT_VISIBLE
            result[BodyRegion.LEGS] = Visibility.NOT_VISIBLE
        if p.y1 <= my:                          # cortada em cima -> cabeça/olhos
            result[BodyRegion.HEAD] = Visibility.NOT_VISIBLE
            result[BodyRegion.EYES] = Visibility.NOT_VISIBLE
        if p.x1 <= mx:                          # cortada à esquerda
            result[BodyRegion.LEFT_HAND] = Visibility.NOT_VISIBLE
        if p.x2 >= obs.frame_width - mx:        # cortada à direita
            result[BodyRegion.RIGHT_HAND] = Visibility.NOT_VISIBLE

        return result

    @staticmethod
    def _within(box: BoundingBox, frame: BoundingBox) -> bool:
        """A região precisa estar essencialmente dentro dos limites do frame."""
        return (
            box.x1 >= frame.x1
            and box.y1 >= frame.y1
            and box.x2 <= frame.x2
            and box.y2 <= frame.y2
        )

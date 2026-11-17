"""
Estimativa de regiões corporais (pose).

PoseProvider abstrai a origem das regiões. HeuristicPose deriva as regiões das
proporções da caixa da pessoa (sem dependências), suficiente para gating de
visibilidade e posicionamento. YoloPoseProvider (stub, import protegido)
usaria keypoints reais quando maior precisão for necessária (seção 9).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.enums import BodyRegion
from app.geometry import BoundingBox
from app.regions import region_bbox


class PoseProvider(ABC):
    @abstractmethod
    def regions(self, person_bbox: BoundingBox, frame: Any = None) -> dict[BodyRegion, BoundingBox]:
        """Retorna a bbox estimada de cada região corporal."""


class HeuristicPose(PoseProvider):
    def regions(self, person_bbox: BoundingBox, frame: Any = None) -> dict[BodyRegion, BoundingBox]:
        return {r: region_bbox(person_bbox, r) for r in BodyRegion}


class YoloPoseProvider(PoseProvider):  # pragma: no cover
    """Usa keypoints de um modelo de pose (ex.: YOLOv8-pose). Import protegido."""

    def __init__(self, model_path: str = "yolov8n-pose.pt") -> None:
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:
            raise RuntimeError("YoloPoseProvider requer `pip install ultralytics`.") from exc
        self._model = YOLO(model_path)

    def regions(self, person_bbox: BoundingBox, frame: Any = None) -> dict[BodyRegion, BoundingBox]:
        # Implementação real: rodar self._model(frame), extrair keypoints
        # (nariz, olhos, punhos, tornozelos...) e montar as regiões a partir
        # deles. Aqui cai no heurístico como salvaguarda.
        return HeuristicPose().regions(person_bbox, frame)


def build_pose_provider(name: str) -> PoseProvider:
    if name == "heuristic":
        return HeuristicPose()
    if name == "yolo":
        return YoloPoseProvider()
    raise ValueError(f"Provider de pose desconhecido: {name!r}")

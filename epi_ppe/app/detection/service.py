"""
Serviços de detecção.

ObjectDetectionService aplica thresholds por classe e NMS sobre a saída crua do
provider. PersonDetectionService e PPEDetectionService são fachadas finas que
mantêm o resto do sistema desacoplado (seção 2 do spec).
"""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.detection.base import ObjectDetectionProvider
from app.enums import PPE_CLASSES, DetectionClass
from app.geometry import iou
from app.types import Detection


class ObjectDetectionService:
    def __init__(self, provider: ObjectDetectionProvider, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings

    @property
    def model_version(self) -> str:
        return self._provider.model_version

    @property
    def is_ready(self) -> bool:
        return self._provider.is_ready

    def load(self) -> None:
        self._provider.load_model()

    def threshold_for(self, cls: DetectionClass) -> float:
        s = self._settings
        table = {
            DetectionClass.PERSON: s.person_confidence_threshold,
            DetectionClass.HELMET: s.helmet_confidence_threshold,
            DetectionClass.SAFETY_VEST: s.vest_confidence_threshold,
            DetectionClass.GLOVES: s.glove_confidence_threshold,
            DetectionClass.SAFETY_BOOTS: s.boots_confidence_threshold,
            DetectionClass.SAFETY_GLASSES: s.glasses_confidence_threshold,
            DetectionClass.EAR_PROTECTION: s.ear_confidence_threshold,
        }
        return table.get(cls, s.default_confidence_threshold)

    def detect(self, frame: Any) -> list[Detection]:
        raw = self._provider.detect(frame)
        kept = [d for d in raw if d.confidence >= self.threshold_for(d.cls)]
        return self._nms(kept, self._settings.nms_iou_threshold)

    @staticmethod
    def _nms(detections: list[Detection], iou_thr: float) -> list[Detection]:
        """Supressão não-máxima por classe."""
        result: list[Detection] = []
        by_cls: dict[DetectionClass, list[Detection]] = {}
        for d in detections:
            by_cls.setdefault(d.cls, []).append(d)
        for group in by_cls.values():
            group.sort(key=lambda d: d.confidence, reverse=True)
            keep: list[Detection] = []
            for cand in group:
                if all(iou(cand.bbox, k.bbox) < iou_thr for k in keep):
                    keep.append(cand)
            result.extend(keep)
        return result


class PersonDetectionService:
    def __init__(self, detector: ObjectDetectionService) -> None:
        self._detector = detector

    def detect(self, frame: Any) -> list[Detection]:
        return [d for d in self._detector.detect(frame) if d.cls == DetectionClass.PERSON]


class PPEDetectionService:
    def __init__(self, detector: ObjectDetectionService) -> None:
        self._detector = detector

    def detect(self, frame: Any) -> list[Detection]:
        return [d for d in self._detector.detect(frame) if d.cls in PPE_CLASSES]

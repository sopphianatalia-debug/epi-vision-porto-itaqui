"""
Provider MOCK — determinístico, sem dependências pesadas.

O "frame" é um dict que descreve a cena, permitindo simular todos os cenários
de teste (múltiplas pessoas, oclusão, EPIs presentes/ausentes, falsos
positivos, etc.) de forma reproduzível.

Formato do frame:
    {
      "detections": [
        {"cls": "PERSON", "confidence": 0.95, "bbox": [x1,y1,x2,y2]},
        {"cls": "HELMET", "confidence": 0.9,  "bbox": [x1,y1,x2,y2]}
      ]
    }
"""
from __future__ import annotations

from typing import Any

from app.detection.base import ObjectDetectionProvider
from app.enums import DetectionClass
from app.types import BoundingBox, Detection


class MockDetector(ObjectDetectionProvider):
    def __init__(self, model_version: str = "mock-detector-v1") -> None:
        self._model_version = model_version
        self._ready = False

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def is_ready(self) -> bool:
        return self._ready

    def load_model(self) -> None:
        self._ready = True

    def detect(self, frame: Any) -> list[Detection]:
        if not self._ready:
            self.load_model()
        detections: list[Detection] = []
        for spec in (frame or {}).get("detections", []):
            detections.append(
                Detection(
                    cls=DetectionClass(spec["cls"]),
                    confidence=float(spec.get("confidence", 0.9)),
                    bbox=BoundingBox(*spec["bbox"]),
                )
            )
        return detections

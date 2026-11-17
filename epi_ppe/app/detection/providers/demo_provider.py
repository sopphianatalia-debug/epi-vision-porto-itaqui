"""
Provider DEMO — gera detecções sintéticas em movimento, escaladas ao tamanho
do frame. Serve para ver o visualizador funcionando (caixas, tracking, FPS,
associação) SEM precisar de um modelo YOLO treinado nem de câmera real.

Uma "pessoa" atravessa a cena com capacete, colete e botas associados.
"""
from __future__ import annotations

import math
from typing import Any

from app.detection.base import ObjectDetectionProvider
from app.enums import DetectionClass
from app.types import BoundingBox, Detection


class DemoDetector(ObjectDetectionProvider):
    def __init__(self) -> None:
        self._ready = False
        self._t = 0

    @property
    def model_version(self) -> str:
        return "demo-synthetic-v1"

    @property
    def is_ready(self) -> bool:
        return self._ready

    def load_model(self) -> None:
        self._ready = True

    def _frame_size(self, frame: Any) -> tuple[int, int]:
        # frame numpy (H, W, C) do OpenCV; fallback para 960x600.
        try:
            h, w = frame.shape[:2]
            return int(w), int(h)
        except Exception:
            return 960, 600

    def detect(self, frame: Any) -> list[Detection]:
        if not self._ready:
            self.load_model()
        self._t += 1
        w, h = self._frame_size(frame)

        pw, ph = 0.22 * w, 0.72 * h
        # movimento horizontal suave (vai e volta), com margem nas bordas
        margin = 0.05 * w
        travel = w - pw - 2 * margin
        x1 = margin + (0.5 * (1 + math.sin(self._t * 0.06))) * travel
        y1 = 0.14 * h
        person = BoundingBox(x1, y1, x1 + pw, y1 + ph)

        def rel(a_top, a_bot, side_pad=0.20, conf=0.93):
            bx1 = person.x1 + side_pad * pw
            bx2 = person.x2 - side_pad * pw
            by1 = person.y1 + a_top * ph
            by2 = person.y1 + a_bot * ph
            return BoundingBox(bx1, by1, bx2, by2), conf

        # confiança oscilando levemente para parecer "vivo"
        jitter = 0.03 * math.sin(self._t * 0.2)
        helmet, hc = rel(0.02, 0.16, side_pad=0.28, conf=0.96 + jitter)
        vest, vc = rel(0.28, 0.62, side_pad=0.12, conf=0.94 + jitter)
        boots, bc = rel(0.88, 0.99, side_pad=0.14, conf=0.90 + jitter)

        return [
            Detection(DetectionClass.PERSON, 0.97, person),
            Detection(DetectionClass.HELMET, min(0.99, hc), helmet),
            Detection(DetectionClass.SAFETY_VEST, min(0.99, vc), vest),
            Detection(DetectionClass.SAFETY_BOOTS, min(0.99, bc), boots),
        ]

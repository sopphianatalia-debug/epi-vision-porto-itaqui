"""
Provider YOLO (Ultralytics) — referência de produção.

Import protegido: torch/ultralytics/opencv só carregam quando este provider é
selecionado, mantendo o núcleo e os testes livres de dependências pesadas.

Instalação:
    pip install ultralytics opencv-python-headless

O mapeamento nome-da-classe -> DetectionClass deve refletir as classes do
modelo treinado no dataset do projeto (ver docs/classes.md).
"""
from __future__ import annotations

from typing import Any

from app.detection.base import ObjectDetectionProvider
from app.enums import DetectionClass
from app.types import BoundingBox, Detection

# Ajuste conforme os nomes de classe do modelo treinado.
DEFAULT_NAME_MAP = {
    "person": DetectionClass.PERSON,
    "helmet": DetectionClass.HELMET,
    "hardhat": DetectionClass.HELMET,
    "safety_vest": DetectionClass.SAFETY_VEST,
    "safety vest": DetectionClass.SAFETY_VEST,  # nome no dataset Roboflow Construction-Site-Safety
    "vest": DetectionClass.SAFETY_VEST,
    "gloves": DetectionClass.GLOVES,
    "safety_boots": DetectionClass.SAFETY_BOOTS,
    "boots": DetectionClass.SAFETY_BOOTS,
    "safety_glasses": DetectionClass.SAFETY_GLASSES,
    "goggles": DetectionClass.SAFETY_GLASSES,
    "ear_protection": DetectionClass.EAR_PROTECTION,
}


class YoloDetector(ObjectDetectionProvider):
    def __init__(self, model_path: str = "yolov8n.pt", device: str = "auto",
                 name_map: dict | None = None) -> None:
        self._model_path = model_path
        self._device = device
        self._name_map = name_map or DEFAULT_NAME_MAP
        self._model = None

    @property
    def model_version(self) -> str:
        return f"yolo:{self._model_path}"

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def load_model(self) -> None:  # pragma: no cover
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "YoloDetector requer `pip install ultralytics opencv-python-headless`."
            ) from exc
        self._model = YOLO(self._model_path)

    def detect(self, frame: Any) -> list[Detection]:  # pragma: no cover
        if self._model is None:
            self.load_model()
        results = self._model.predict(frame, device=None if self._device == "auto" else self._device,
                                      verbose=False)
        detections: list[Detection] = []
        names = self._model.names
        for r in results:
            for box in r.boxes:
                raw_name = str(names[int(box.cls)]).lower()
                mapped = self._name_map.get(raw_name)
                if mapped is None:
                    continue  # classe não relevante para EPI
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                detections.append(
                    Detection(cls=mapped, confidence=float(box.conf), bbox=BoundingBox(x1, y1, x2, y2))
                )
        return detections

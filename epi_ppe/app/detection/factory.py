"""Seleção configurável do provider de detecção."""
from __future__ import annotations

from app.config import Settings
from app.detection.base import ObjectDetectionProvider
from app.detection.service import ObjectDetectionService


def build_provider(settings: Settings) -> ObjectDetectionProvider:
    name = settings.detector_provider.lower()
    if name == "mock":
        from app.detection.providers.mock_provider import MockDetector

        return MockDetector()
    if name == "yolo":
        from app.detection.providers.yolo_provider import DEFAULT_NAME_MAP, YoloDetector

        name_map = dict(DEFAULT_NAME_MAP)
        if settings.detector_name_map_json:
            import json

            try:
                overrides = json.loads(settings.detector_name_map_json)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"PPE_DETECTOR_NAME_MAP_JSON inválido (precisa ser um objeto JSON): {exc}"
                ) from exc
            # Chaves do JSON viram minúsculas (mesmo padrão do YoloDetector,
            # que compara nomes em lowercase); valores viram DetectionClass.
            from app.enums import DetectionClass

            for model_class_name, system_class_name in overrides.items():
                name_map[model_class_name.lower()] = DetectionClass(system_class_name)

        return YoloDetector(model_path=settings.detector_model_path, device=settings.detector_device,
                             name_map=name_map)
    if name == "demo":
        from app.detection.providers.demo_provider import DemoDetector

        return DemoDetector()
    raise ValueError(f"Provider de detecção desconhecido: {settings.detector_provider!r}")


def build_detection_service(settings: Settings) -> ObjectDetectionService:
    service = ObjectDetectionService(build_provider(settings), settings)
    service.load()
    return service

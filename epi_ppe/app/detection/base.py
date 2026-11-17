"""
Camada abstrata ObjectDetectionProvider.

Desacopla o sistema de um modelo específico (seção 3 do spec). Qualquer
detector (YOLO, RT-DETR, etc.) implementa esta interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.types import Detection


class ObjectDetectionProvider(ABC):
    @property
    @abstractmethod
    def model_version(self) -> str:
        ...

    @abstractmethod
    def load_model(self) -> None:
        """Carrega pesos/rede. Idempotente."""

    @abstractmethod
    def detect(self, frame: Any) -> list[Detection]:
        """Retorna todas as detecções (pessoa + EPIs) do frame."""

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        ...

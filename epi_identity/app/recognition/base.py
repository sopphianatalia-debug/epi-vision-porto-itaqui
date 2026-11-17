"""
Camada abstrata FaceRecognitionProvider.

Permite trocar o modelo de reconhecimento (InsightFace/ArcFace, FaceNet, etc.)
sem alterar o restante do sistema. Cada provider expõe apenas as operações
dependentes de modelo; matching e regras ficam fora, no domínio genérico.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.recognition.types import DetectedFace, FaceEmbedding, FaceQuality


class FaceRecognitionProvider(ABC):
    """Contrato dependente de modelo (detectFace/assessFaceQuality/generateEmbedding)."""

    @property
    @abstractmethod
    def model_version(self) -> str:
        ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        ...

    @abstractmethod
    def detect_faces(self, frame: Any) -> list[DetectedFace]:
        """Detecta rostos e retorna bbox + qualidade de cada um."""

    @abstractmethod
    def assess_quality(self, frame: Any, face: DetectedFace) -> FaceQuality:
        """Reavalia/refina a qualidade de um rosto específico."""

    @abstractmethod
    def generate_embedding(self, frame: Any, face: DetectedFace) -> FaceEmbedding:
        """Gera o vetor de características (embedding) do rosto."""

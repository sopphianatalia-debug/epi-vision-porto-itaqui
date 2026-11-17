"""Seleção configurável do provider de reconhecimento."""
from __future__ import annotations

from app.config import Settings
from app.recognition.base import FaceRecognitionProvider


def build_provider(settings: Settings) -> FaceRecognitionProvider:
    name = settings.face_provider.lower()
    if name == "mock":
        from app.recognition.providers.mock_provider import MockFaceProvider

        return MockFaceProvider(
            model_version=settings.face_model_version,
            embedding_dim=settings.embedding_dim,
        )
    if name == "insightface":
        from app.recognition.providers.insightface_provider import InsightFaceProvider

        return InsightFaceProvider(embedding_dim=settings.embedding_dim)

    raise ValueError(f"Provider de reconhecimento desconhecido: {settings.face_provider!r}")

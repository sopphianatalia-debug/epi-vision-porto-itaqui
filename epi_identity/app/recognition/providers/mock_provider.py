"""
Provider MOCK — determinístico, sem dependências pesadas.

Uso: desenvolvimento e testes. Aceita "frames" que são dicts descrevendo a
cena (rostos, qualidade, semente do embedding), permitindo simular todos os
cenários: baixa qualidade, múltiplos rostos, ambiguidade, desconhecido, etc.

Formato do frame:
    {
      "faces": [
        {"bbox": [x1,y1,x2,y2], "quality": 0.92, "seed": "FUNC-000234",
         "single_face": true, "face_visible": true}
      ]
    }
"""
from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from app.recognition.base import FaceRecognitionProvider
from app.recognition.types import (
    BoundingBox,
    DetectedFace,
    FaceEmbedding,
    FaceQuality,
)


class MockFaceProvider(FaceRecognitionProvider):
    def __init__(self, model_version: str = "mock-v1", embedding_dim: int = 512) -> None:
        self._model_version = model_version
        self._embedding_dim = embedding_dim

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def _seed_vector(self, seed: str) -> tuple[float, ...]:
        """Vetor determinístico e normalizado a partir de uma semente textual."""
        digest = hashlib.sha256(seed.encode()).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
        v = rng.standard_normal(self._embedding_dim)
        v = v / np.linalg.norm(v)
        return tuple(float(x) for x in v)

    def detect_faces(self, frame: Any) -> list[DetectedFace]:
        faces_spec = (frame or {}).get("faces", [])
        n = len(faces_spec)
        result: list[DetectedFace] = []
        for spec in faces_spec:
            bbox = BoundingBox(*spec.get("bbox", [0, 0, 100, 100]))
            quality = FaceQuality(
                score=float(spec.get("quality", 0.9)),
                single_face=n == 1 and spec.get("single_face", True),
                face_visible=spec.get("face_visible", True),
            )
            result.append(DetectedFace(bbox=bbox, quality=quality))
        return result

    def assess_quality(self, frame: Any, face: DetectedFace) -> FaceQuality:
        return face.quality

    def generate_embedding(self, frame: Any, face: DetectedFace) -> FaceEmbedding:
        # A semente vem do frame (no mock), simulando "de quem é o rosto".
        seed = ""
        for spec in (frame or {}).get("faces", []):
            if list(spec.get("bbox", [])) == [face.bbox.x1, face.bbox.y1, face.bbox.x2, face.bbox.y2]:
                seed = spec.get("seed", "")
                break
        return FaceEmbedding(
            vector=self._seed_vector(seed or "unknown"),
            model_version=self._model_version,
            quality_score=face.quality.score,
        )

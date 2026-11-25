"""
Provider InsightFace/ArcFace (referência de produção).

Import protegido: a dependência pesada (insightface, onnxruntime) só é
carregada quando este provider é efetivamente selecionado, mantendo o resto
do sistema (e os testes) livres de dependências de visão computacional.

Instalação:
    pip install insightface onnxruntime
"""
from __future__ import annotations

import threading
from typing import Any

from app.recognition.base import FaceRecognitionProvider
from app.recognition.image import InvalidImageError, decode_image, is_image_payload
from app.recognition.types import (
    BoundingBox,
    DetectedFace,
    FaceEmbedding,
    FaceQuality,
)


MIN_FACE_PX = 60   # rosto menor que isso (lado menor da caixa) não rende embedding confiável


class InsightFaceProvider(FaceRecognitionProvider):
    def __init__(self, model_name: str = "buffalo_l", embedding_dim: int = 512) -> None:
        try:
            from insightface.app import FaceAnalysis  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "InsightFaceProvider requer `pip install insightface onnxruntime`."
            ) from exc

        self._model_name = model_name
        self._embedding_dim = embedding_dim
        # CPU de propósito (funciona em qualquer máquina do grupo, inclusive Mac sem CUDA).
        self._app = FaceAnalysis(name=model_name, providers=["CPUExecutionProvider"])
        self._app.prepare(ctx_id=0, det_size=(640, 640))
        # Uma só inferência por quadro: detect_faces guarda o resultado e generate_embedding o reaproveita.
        self._lock = threading.Lock()
        self._last: tuple[Any, list[Any]] | None = None

    @property
    def model_version(self) -> str:
        return f"insightface:{self._model_name}"

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def _analyze(self, frame: Any) -> list[Any]:  # pragma: no cover
        """Roda o modelo uma vez por quadro. `frame` é o payload {"image_base64": ...} ou um ndarray BGR."""
        with self._lock:
            if self._last is not None and self._last[0] is frame:
                return self._last[1]
            if is_image_payload(frame):
                image = decode_image(frame)
            elif hasattr(frame, "shape"):
                image = frame
            else:
                raise InvalidImageError("O quadro não contém uma imagem (esperado image_base64).")
            faces = list(self._app.get(image))
            self._last = (frame, faces)     # guarda a referência ao quadro: o `is` não confunde com outro objeto
            return faces

    def detect_faces(self, frame: Any) -> list[DetectedFace]:  # pragma: no cover
        faces = self._analyze(frame)
        detected: list[DetectedFace] = []
        for f in faces:
            x1, y1, x2, y2 = f.bbox
            quality = self._quality_from_face(f, num_faces=len(faces))
            detected.append(DetectedFace(BoundingBox(x1, y1, x2, y2), quality))
        return detected

    def assess_quality(self, frame: Any, face: DetectedFace) -> FaceQuality:  # pragma: no cover
        return face.quality

    def generate_embedding(self, frame: Any, face: DetectedFace) -> FaceEmbedding:  # pragma: no cover
        faces = self._analyze(frame)
        target = self._closest(faces, face.bbox)
        vector = tuple(float(x) for x in target.normed_embedding)
        return FaceEmbedding(vector, self.model_version, face.quality.score)

    # --- helpers ---
    def _quality_from_face(self, f: Any, num_faces: int) -> FaceQuality:  # pragma: no cover
        det_score = float(getattr(f, "det_score", 1.0))
        pose = getattr(f, "pose", None)
        pose_ok = True if pose is None else max(abs(p) for p in pose) < 30.0
        x1, y1, x2, y2 = (float(v) for v in f.bbox)
        big_enough = min(x2 - x1, y2 - y1) >= MIN_FACE_PX
        reasons = () if big_enough else ("face_too_small",)
        return FaceQuality(
            score=det_score,
            single_face=num_faces == 1,
            pose_ok=pose_ok,
            resolution_ok=big_enough,
            face_visible=det_score > 0.5 and big_enough,
            reasons=reasons,
        )

    def _closest(self, faces: list[Any], bbox: BoundingBox) -> Any:  # pragma: no cover
        def center_dist(f: Any) -> float:
            fx = (f.bbox[0] + f.bbox[2]) / 2
            fy = (f.bbox[1] + f.bbox[3]) / 2
            cx = (bbox.x1 + bbox.x2) / 2
            cy = (bbox.y1 + bbox.y2) / 2
            return (fx - cx) ** 2 + (fy - cy) ** 2

        return min(faces, key=center_dist)

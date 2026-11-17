"""
CameraService — abstração de fontes de vídeo (seções 11 e 12 do spec).

Fontes suportadas: RTSP, arquivo de vídeo, webcam e stream de teste (mock).
Trata falhas de forma resiliente: câmera offline, frame inválido, perda de
conexão — sem derrubar o pipeline.

O backend real de captura (OpenCV) é isolado no RtspCamera/FileCamera, com
import protegido. O TestCamera não exige nada além da stdlib.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional

from app.enums import CameraState


class CameraError(Exception):
    pass


class CameraService(ABC):
    def __init__(self, camera_id: str) -> None:
        self.camera_id = camera_id
        self.state = CameraState.CONNECTING

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def read(self) -> Optional[Any]:
        """Retorna o próximo frame, ou None se indisponível/fim do stream."""

    @abstractmethod
    def close(self) -> None: ...

    def frames(self, max_frames: Optional[int] = None) -> Iterator[Any]:
        """
        Gera frames com tolerância a falhas: frames None são pulados; ao fim
        do stream (ou após muitas falhas seguidas) o loop termina.
        """
        self.open()
        produced, consecutive_failures = 0, 0
        while max_frames is None or produced < max_frames:
            try:
                frame = self.read()
            except Exception:
                self.state = CameraState.ERROR
                consecutive_failures += 1
                if consecutive_failures >= 30:
                    break
                continue
            if frame is None:
                consecutive_failures += 1
                if consecutive_failures >= 30:
                    self.state = CameraState.OFFLINE
                    break
                continue
            consecutive_failures = 0
            self.state = CameraState.ONLINE
            produced += 1
            yield frame
        self.close()


class TestCamera(CameraService):
    """Emite uma lista pré-definida de frames (dicts de cena) para testes."""

    __test__ = False  # impede o pytest de coletar esta classe como testes

    def __init__(self, camera_id: str, scripted_frames: list[Any]) -> None:
        super().__init__(camera_id)
        self._frames = scripted_frames
        self._idx = 0

    def open(self) -> None:
        self.state = CameraState.ONLINE
        self._idx = 0

    def read(self) -> Optional[Any]:
        if self._idx >= len(self._frames):
            return None
        frame = self._frames[self._idx]
        self._idx += 1
        return frame

    def close(self) -> None:
        self.state = CameraState.OFFLINE


class OpenCVCamera(CameraService):
    """Câmera RTSP / arquivo / webcam via OpenCV (import protegido)."""

    def __init__(self, camera_id: str, source: Any) -> None:  # pragma: no cover
        super().__init__(camera_id)
        self._source = source
        self._cap = None

    def open(self) -> None:  # pragma: no cover
        try:
            import cv2  # type: ignore
        except ImportError as exc:
            raise CameraError("OpenCVCamera requer `pip install opencv-python-headless`.") from exc
        self._cap = cv2.VideoCapture(self._source)
        if not self._cap.isOpened():
            self.state = CameraState.OFFLINE
            raise CameraError(f"Não foi possível abrir a fonte: {self._source!r}")
        self.state = CameraState.ONLINE

    def read(self) -> Optional[Any]:  # pragma: no cover
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:  # pragma: no cover
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self.state = CameraState.OFFLINE

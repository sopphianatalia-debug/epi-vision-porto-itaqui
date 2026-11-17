"""
PPEPipeline — orquestra o fluxo do Módulo 2 (seção 2 do spec):

  frame → detecção → separa pessoas/EPIs → tracking (person_track_id)
        → associação pessoa↔EPI → resultado estruturado

DetectionEventService guarda os últimos eventos em memória (janela móvel),
prontos para o Módulo 3 e para a interface de teste.
"""
from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from app.association import PersonPPEAssociator
from app.config import Settings
from app.detection import ObjectDetectionService
from app.enums import PPE_CLASSES, DetectionClass
from app.observability.metrics import metrics
from app.tracking import PersonTracker
from app.types import PersonResult


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DetectionEventService:
    def __init__(self, maxlen: int = 500) -> None:
        self._events = deque(maxlen=maxlen)

    def add(self, event: dict) -> None:
        self._events.append(event)

    def recent(self, limit: int = 50) -> list[dict]:
        return list(self._events)[-limit:][::-1]


class PPEPipeline:
    def __init__(
        self,
        detector: ObjectDetectionService,
        tracker: PersonTracker,
        associator: PersonPPEAssociator,
        events: Optional[DetectionEventService] = None,
    ) -> None:
        self._detector = detector
        self._tracker = tracker
        self._associator = associator
        self._events = events or DetectionEventService()

    @property
    def events(self) -> DetectionEventService:
        return self._events

    def process_frame(self, camera_id: str, frame: Any) -> list[PersonResult]:
        pipeline_start = time.perf_counter()

        infer_start = time.perf_counter()
        detections = self._detector.detect(frame)
        inference_ms = (time.perf_counter() - infer_start) * 1000.0

        persons = [d for d in detections if d.cls == DetectionClass.PERSON]
        ppes = [d for d in detections if d.cls in PPE_CLASSES]

        tracked = self._tracker.update(persons)          # [(track_id, Detection)]
        results = self._associator.associate(tracked, ppes)

        pipeline_ms = (time.perf_counter() - pipeline_start) * 1000.0
        metrics.record_frame(inference_ms, pipeline_ms)

        timestamp = _utc_iso()
        for r in results:
            self._events.add(r.to_dict(camera_id, timestamp))
        return results

    def process_stream(self, camera, max_frames: Optional[int] = None) -> list[list[PersonResult]]:
        """Processa uma fonte de vídeo (CameraService) frame a frame."""
        out: list[list[PersonResult]] = []
        for frame in camera.frames(max_frames=max_frames):
            out.append(self.process_frame(camera.camera_id, frame))
        return out

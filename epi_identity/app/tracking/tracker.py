"""
Tracking leve por IoU.

Gera e mantém identificadores TEMPORÁRIOS (person_track_id), ex.:
CAM07_PERSON_00127. Não sabe nada sobre identidade real — essa associação
é feita separadamente pelo IdentityManager.

Em produção pode ser substituído por ByteTrack/DeepSORT mantendo a interface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.enums import TrackState
from app.recognition.types import BoundingBox


@dataclass(frozen=True)
class Detection:
    bbox: BoundingBox


@dataclass
class Track:
    track_code: str
    camera_id: str
    bbox: BoundingBox
    first_seen: datetime
    last_seen: datetime
    state: TrackState = TrackState.ACTIVE
    hits: int = 1


def iou(a: BoundingBox, b: BoundingBox) -> float:
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


class IoUTracker:
    def __init__(self, camera_id: str, iou_threshold: float = 0.3, track_ttl_seconds: int = 15) -> None:
        self.camera_id = camera_id
        self.iou_threshold = iou_threshold
        self.track_ttl_seconds = track_ttl_seconds
        self._tracks: dict[str, Track] = {}
        self._counter = 0

    @property
    def active_tracks(self) -> list[Track]:
        return [t for t in self._tracks.values() if t.state == TrackState.ACTIVE]

    def _new_code(self) -> str:
        self._counter += 1
        return f"{self.camera_id}_PERSON_{self._counter:05d}"

    def update(self, detections: list[Detection], now: datetime) -> list[Track]:
        """Associa detecções a tracks existentes (IoU) ou cria novos; expira antigos."""
        available = list(self.active_tracks)
        matched_codes: set[str] = set()

        for det in detections:
            best_track = None
            best_iou = self.iou_threshold
            for track in available:
                if track.track_code in matched_codes:
                    continue
                score = iou(track.bbox, det.bbox)
                if score >= best_iou:
                    best_iou = score
                    best_track = track

            if best_track is not None:
                best_track.bbox = det.bbox
                best_track.last_seen = now
                best_track.hits += 1
                matched_codes.add(best_track.track_code)
            else:
                code = self._new_code()
                self._tracks[code] = Track(
                    track_code=code,
                    camera_id=self.camera_id,
                    bbox=det.bbox,
                    first_seen=now,
                    last_seen=now,
                )
                matched_codes.add(code)

        self._expire(now)
        return self.active_tracks

    def _expire(self, now: datetime) -> None:
        for track in self._tracks.values():
            if track.state != TrackState.ACTIVE:
                continue
            if (now - track.last_seen).total_seconds() > self.track_ttl_seconds:
                track.state = TrackState.CLOSED

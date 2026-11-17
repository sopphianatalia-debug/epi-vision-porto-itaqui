"""
Tracking de pessoas por IoU.

Gera person_track_id no formato TRACK-000123 e mantém a mesma identidade da
pessoa ao longo dos frames, reduzindo duplicações (seção 7 do spec).
Interface trocável por ByteTrack/DeepSORT sem afetar o pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.geometry import iou
from app.types import BoundingBox, Detection


@dataclass
class PersonTrack:
    track_id: str
    bbox: BoundingBox
    confidence: float
    frames_since_seen: int = 0
    hits: int = 1
    active: bool = True


class PersonTracker:
    def __init__(self, iou_threshold: float = 0.3, track_ttl_frames: int = 30) -> None:
        self.iou_threshold = iou_threshold
        self.track_ttl_frames = track_ttl_frames
        self._tracks: dict[str, PersonTrack] = {}
        self._counter = 0

    @property
    def active_tracks(self) -> list[PersonTrack]:
        return [t for t in self._tracks.values() if t.active]

    def _new_id(self) -> str:
        self._counter += 1
        return f"TRACK-{self._counter:06d}"

    def update(self, persons: list[Detection]) -> list[tuple[str, Detection]]:
        """
        Associa detecções de pessoa a tracks (IoU) ou cria novos.
        Retorna [(track_id, Detection), ...] para o frame atual.
        """
        for t in self.active_tracks:
            t.frames_since_seen += 1

        assignments: list[tuple[str, Detection]] = []
        matched: set[str] = set()

        for det in persons:
            best_track = None
            best_iou = self.iou_threshold
            for t in self.active_tracks:
                if t.track_id in matched:
                    continue
                score = iou(t.bbox, det.bbox)
                if score >= best_iou:
                    best_iou = score
                    best_track = t

            if best_track is not None:
                best_track.bbox = det.bbox
                best_track.confidence = det.confidence
                best_track.frames_since_seen = 0
                best_track.hits += 1
                matched.add(best_track.track_id)
                assignments.append((best_track.track_id, det))
            else:
                tid = self._new_id()
                self._tracks[tid] = PersonTrack(track_id=tid, bbox=det.bbox, confidence=det.confidence)
                matched.add(tid)
                assignments.append((tid, det))

        self._expire()
        return assignments

    def _expire(self) -> None:
        for t in self._tracks.values():
            if t.active and t.frames_since_seen > self.track_ttl_frames:
                t.active = False

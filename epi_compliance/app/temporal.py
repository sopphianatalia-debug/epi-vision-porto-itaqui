"""
Agregação temporal (seção 8 do spec).

Em vez de decidir por um único frame, mantém uma janela deslizante por
(person_track_id, chave_do_EPI). O status final é o dominante na janela,
ponderado por confiança, e a confiança final cresce com o acordo entre frames
(reduzindo falsos positivos). NOT_VISIBLE nunca vira UNKNOWN — é um estado
definido, não incerteza sobre presença.
"""
from __future__ import annotations

from collections import defaultdict, deque

from app.config import Settings
from app.enums import PPEStatus
from app.types import FrameAssessment, PPEResult


class TemporalAggregator:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._windows: dict[tuple[str, str], deque[FrameAssessment]] = defaultdict(
            lambda: deque(maxlen=settings.temporal_window)
        )

    def push(self, track_id: str, key: str, assessment: FrameAssessment) -> PPEResult:
        window = self._windows[(track_id, key)]
        window.append(assessment)
        return self._aggregate(window)

    def reset(self, track_id: str) -> None:
        for k in [k for k in self._windows if k[0] == track_id]:
            del self._windows[k]

    def _aggregate(self, window: deque[FrameAssessment]) -> PPEResult:
        n = len(window)
        # Voto ponderado por confiança para achar o status dominante.
        weights: dict[PPEStatus, float] = {}
        for a in window:
            weights[a.status] = weights.get(a.status, 0.0) + a.confidence
        dominant = max(weights, key=weights.get)

        same = [a for a in window if a.status == dominant]
        agreement = len(same) / n
        mean_conf = sum(a.confidence for a in same) / len(same)

        # Penaliza janela ainda pouco preenchida.
        fill = min(1.0, n / self._s.temporal_min_frames)
        confidence = mean_conf * agreement * fill

        # NOT_VISIBLE é definitivo: reporta como está, sem virar UNKNOWN.
        if dominant == PPEStatus.NOT_VISIBLE:
            return PPEResult(PPEStatus.NOT_VISIBLE, max(confidence, 0.5), "region_not_visible")

        # Confiança insuficiente -> UNKNOWN (não arriscar conclusão).
        if confidence < self._s.confidence_threshold:
            return PPEResult(PPEStatus.UNKNOWN, confidence, "low_confidence")

        note = ""
        if (
            dominant == PPEStatus.PROPER
            and agreement >= self._s.high_confidence_agreement
            and n >= self._s.temporal_window
        ):
            note = "HIGH_CONFIDENCE_PROPER_USE"
        return PPEResult(dominant, confidence, note)

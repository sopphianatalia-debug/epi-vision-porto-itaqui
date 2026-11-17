"""
Métricas de observabilidade da fusão.

Além das métricas globais (usadas por GET /fusion/metrics), esta classe agrega
saúde OPERACIONAL por câmera (GET /fusion/cameras/health). A extensão é apenas
observabilidade: agrega sinais que o FusionService já processa (camera_id,
confidence, status, participação em conflito). Não altera a lógica de fusão e não
armazena nenhum dado biométrico.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Iterable, Optional


@dataclass
class _CameraAgg:
    """Agregador incremental por câmera (contadores cumulativos)."""

    observations: int = 0
    matches: int = 0
    anonymous: int = 0
    conflicts: int = 0            # participações/contribuições em conflitos
    confidence_sum: float = 0.0
    confidence_count: int = 0     # nº de observações com confidence informativa
    not_visible: int = 0          # nº de observações com ao menos um EPI NOT_VISIBLE


class FusionMetrics:
    # Pesos do health_score (documentados no README). Somam 1.0.
    W_IDENTITY = 0.35
    W_CONFIDENCE = 0.25
    W_NOT_VISIBLE = 0.20
    W_CONFLICT = 0.20

    def __init__(self, window: int = 300) -> None:
        self._lock = Lock()
        self._obs_total = 0
        self._identity_matched = 0
        self._identity_rejected = 0
        self._conflicts = 0
        self._expired = 0
        self._latencies = deque(maxlen=window)
        self._obs_times = deque(maxlen=1000)
        self._by_camera: dict[str, int] = defaultdict(int)
        self._by_employee: dict[str, int] = defaultdict(int)
        self._active_states = 0
        self._anonymous = 0
        # NOVO: agregador de saúde por câmera
        self._camera_agg: dict[str, _CameraAgg] = defaultdict(_CameraAgg)

    # ------------------------------------------------------------------ #
    # Registro (chamado pelo FusionService)
    # ------------------------------------------------------------------ #
    def record_observation(
        self,
        camera_id: str,
        latency_ms: float,
        matched: bool,
        employee_id: Optional[str],
        confidence: Optional[float] = None,
        not_visible: bool = False,
    ) -> None:
        with self._lock:
            self._obs_total += 1
            self._latencies.append(latency_ms)
            self._obs_times.append(time.monotonic())
            self._by_camera[camera_id] += 1
            if matched and employee_id:
                self._identity_matched += 1
                self._by_employee[employee_id] += 1
            else:
                self._identity_rejected += 1
                self._anonymous += 1

            # Agregação por câmera (observabilidade)
            agg = self._camera_agg[camera_id]
            agg.observations += 1
            if matched and employee_id:
                agg.matches += 1
            else:
                agg.anonymous += 1
            if confidence is not None:
                agg.confidence_sum += confidence
                agg.confidence_count += 1
            if not_visible:
                agg.not_visible += 1

    def record_conflict(self, camera_ids: Iterable[str] = ()) -> None:
        with self._lock:
            self._conflicts += 1
            # Atribuição por câmera: cada câmera que contribuiu com evidência para
            # o conflito recebe +1. (Participação no conflito, não "gerou sozinha".)
            for cam in {c for c in camera_ids if c}:
                self._camera_agg[cam].conflicts += 1

    def record_expired(self, n: int = 1) -> None:
        with self._lock:
            self._expired += n

    def set_active_states(self, n: int) -> None:
        with self._lock:
            self._active_states = n

    # ------------------------------------------------------------------ #
    # Cálculos auxiliares
    # ------------------------------------------------------------------ #
    def _obs_per_second(self) -> float:
        now = time.monotonic()
        recent = [t for t in self._obs_times if now - t <= 1.0]
        return float(len(recent))

    @staticmethod
    def _rate(numer: int, denom: int) -> Optional[float]:
        if denom <= 0:
            return None
        return numer / denom

    @classmethod
    def _health_score(
        cls,
        identity_match_rate: Optional[float],
        avg_confidence: Optional[float],
        not_visible_rate: Optional[float],
        conflict_rate: Optional[float],
    ) -> Optional[float]:
        """
        Score determinístico 0..100 (maior = melhor). Cada componente ausente
        (null) é descartado e os pesos remanescentes são renormalizados, de modo
        que a câmera não seja penalizada por um dado que ela não pode fornecer.
        Se nenhum componente for calculável, retorna null.
        """
        components: list[tuple[float, float]] = []  # (peso, valor 0..100)
        if identity_match_rate is not None:
            components.append((cls.W_IDENTITY, identity_match_rate * 100.0))
        if avg_confidence is not None:
            components.append((cls.W_CONFIDENCE, avg_confidence * 100.0))
        if not_visible_rate is not None:
            components.append((cls.W_NOT_VISIBLE, (1.0 - not_visible_rate) * 100.0))
        if conflict_rate is not None:
            components.append((cls.W_CONFLICT, (1.0 - conflict_rate) * 100.0))

        total_weight = sum(w for w, _ in components)
        if total_weight <= 0:
            return None
        score = sum(w * v for w, v in components) / total_weight
        return round(max(0.0, min(100.0, score)), 2)

    def _camera_health_locked(self, camera_id: str, agg: _CameraAgg) -> dict:
        obs = agg.observations
        identity_match_rate = self._rate(agg.matches, obs)
        not_visible_rate = self._rate(agg.not_visible, obs)
        avg_confidence = (agg.confidence_sum / agg.confidence_count
                          if agg.confidence_count > 0 else None)
        raw_conflict_rate = self._rate(agg.conflicts, obs)
        # conflitos podem exceder observações (1 obs participa de vários EPIs);
        # limita a taxa a [0,1] para o componente do score.
        conflict_rate = None if raw_conflict_rate is None else min(raw_conflict_rate, 1.0)

        return {
            "camera_id": camera_id,
            "observations": obs,
            "identity_matches": agg.matches,
            "identity_match_rate": None if identity_match_rate is None else round(identity_match_rate, 4),
            "anonymous": agg.anonymous,
            "conflicts": agg.conflicts,
            "avg_confidence": None if avg_confidence is None else round(avg_confidence, 4),
            "not_visible": agg.not_visible,
            "not_visible_rate": None if not_visible_rate is None else round(not_visible_rate, 4),
            "health_score": self._health_score(
                identity_match_rate, avg_confidence, not_visible_rate, conflict_rate
            ),
        }

    def camera_health(self) -> list[dict]:
        """Saúde por câmera, ordenada da PIOR para a MELHOR (health_score crescente).

        Câmeras com health_score = null (sem dados suficientes) vão para o fim.
        """
        with self._lock:
            rows = [self._camera_health_locked(cam, agg)
                    for cam, agg in self._camera_agg.items()]
        rows.sort(key=lambda r: (r["health_score"] is None, r["health_score"] if r["health_score"] is not None else 0.0))
        return rows

    # ------------------------------------------------------------------ #
    # Snapshot global (INALTERADO — compatibilidade com /fusion/metrics)
    # ------------------------------------------------------------------ #
    def snapshot(self) -> dict:
        with self._lock:
            total = self._obs_total or 1
            avg_latency = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0
            return {
                "observations_total": self._obs_total,
                "observations_per_second": self._obs_per_second(),
                "fusion_latency_ms": round(avg_latency, 3),
                "active_employee_states": self._active_states,
                "anonymous_observations": self._anonymous,
                "fusion_conflicts": self._conflicts,
                "expired_states": self._expired,
                "identity_match_rate": round(self._identity_matched / total, 4),
                "observations_by_camera": dict(self._by_camera),
                "observations_by_employee": dict(self._by_employee),
            }


metrics = FusionMetrics()

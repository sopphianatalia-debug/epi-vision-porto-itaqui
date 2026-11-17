"""
Métricas de performance (seção 10 do spec): FPS, latência, tempo de inferência.

Coletor em memória com janela móvel. Em produção, exportar para
Prometheus/OpenTelemetry preservando os nomes.
"""
from __future__ import annotations

from collections import deque
from threading import Lock


class PerformanceMetrics:
    def __init__(self, window: int = 200) -> None:
        self._inference_ms = deque(maxlen=window)
        self._pipeline_ms = deque(maxlen=window)
        self._frames = 0
        self._lock = Lock()

    def record_frame(self, inference_ms: float, pipeline_ms: float) -> None:
        with self._lock:
            self._frames += 1
            self._inference_ms.append(inference_ms)
            self._pipeline_ms.append(pipeline_ms)

    @staticmethod
    def _avg(values: deque) -> float:
        return sum(values) / len(values) if values else 0.0

    def snapshot(self) -> dict:
        with self._lock:
            avg_pipe = self._avg(self._pipeline_ms)
            return {
                "frames_processed": self._frames,
                "avg_inference_ms": round(self._avg(self._inference_ms), 2),
                "avg_pipeline_ms": round(avg_pipe, 2),
                "fps": round(1000.0 / avg_pipe, 2) if avg_pipe > 0 else 0.0,
            }


metrics = PerformanceMetrics()

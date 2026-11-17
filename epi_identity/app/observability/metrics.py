"""
Métricas do módulo (seção 16).

Coletor em memória, thread-safe o suficiente para referência. Em produção,
exportar para Prometheus/OpenTelemetry mantendo os mesmos nomes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from app.enums import RecognitionStatus


@dataclass
class RecognitionMetrics:
    people_detected: int = 0
    identified: int = 0
    unknown: int = 0
    low_confidence: int = 0
    ambiguous: int = 0
    unavailable: int = 0
    reidentifications: int = 0
    errors: int = 0
    total_processing_ms: float = 0.0
    recognition_count: int = 0
    # RLock (não Lock): snapshot() chama self.avg_processing_ms enquanto já
    # segura o cadeado, e avg_processing_ms tenta travar de novo — com Lock
    # comum isso trava para sempre (a mesma thread nunca consegue destravar
    # o próprio cadeado). RLock permite reentrância pela mesma thread.
    _lock: RLock = field(default_factory=RLock, repr=False)

    def record(self, status: RecognitionStatus, processing_ms: float) -> None:
        with self._lock:
            self.recognition_count += 1
            self.total_processing_ms += processing_ms
            mapping = {
                RecognitionStatus.MATCHED: "identified",
                RecognitionStatus.UNKNOWN: "unknown",
                RecognitionStatus.LOW_CONFIDENCE: "low_confidence",
                RecognitionStatus.AMBIGUOUS: "ambiguous",
                RecognitionStatus.UNAVAILABLE: "unavailable",
            }
            attr = mapping.get(status)
            if attr:
                setattr(self, attr, getattr(self, attr) + 1)

    @property
    def avg_processing_ms(self) -> float:
        with self._lock:
            if self.recognition_count == 0:
                return 0.0
            return self.total_processing_ms / self.recognition_count

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "people_detected": self.people_detected,
                "identified": self.identified,
                "unknown": self.unknown,
                "low_confidence": self.low_confidence,
                "ambiguous": self.ambiguous,
                "unavailable": self.unavailable,
                "reidentifications": self.reidentifications,
                "errors": self.errors,
                "avg_processing_ms": round(self.avg_processing_ms, 2),
                "recognition_count": self.recognition_count,
            }


metrics = RecognitionMetrics()

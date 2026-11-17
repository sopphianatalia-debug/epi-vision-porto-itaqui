"""
Motor de matching de embeddings.

Regras (seções 7 e 8 do spec):
- similaridade por cosseno contra a galeria autorizada;
- threshold de similaridade e de confiança configuráveis;
- nunca aceitar identificação só porque existe um "melhor" resultado;
- se o 2º colocado estiver dentro de uma margem, retornar AMBIGUOUS.

A calibração similaridade -> confiança abaixo é uma referência. Em produção,
recomenda-se calibração estatística (ex.: Platt scaling) sobre dados reais.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from app.enums import RecognitionStatus
from app.recognition.types import Candidate, IdentificationResult


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class MatchingEngine:
    def __init__(
        self,
        similarity_threshold: float,
        confidence_threshold: float,
        ambiguity_margin: float,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.confidence_threshold = confidence_threshold
        self.ambiguity_margin = ambiguity_margin

    def _confidence(self, best: float, runner: float | None) -> float:
        sim_norm = _clamp((best - self.similarity_threshold) / (1.0 - self.similarity_threshold))
        if runner is None:
            separation = 1.0
        else:
            separation = _clamp((best - runner) / (2.0 * self.ambiguity_margin))
        return _clamp(sim_norm * (0.6 + 0.4 * separation))

    def match(
        self,
        probe: Sequence[float],
        gallery: list[tuple[str, Sequence[float]]],
        model_version: str,
        quality_score: float,
    ) -> IdentificationResult:
        base = dict(
            quality_score=quality_score,
            model_version=model_version,
        )

        if not gallery:
            return IdentificationResult(status=RecognitionStatus.UNKNOWN, **base)

        scored = sorted(
            ((code, cosine_similarity(probe, vec)) for code, vec in gallery),
            key=lambda t: t[1],
            reverse=True,
        )
        best_code, best_sim = scored[0]
        runner = Candidate(scored[1][0], scored[1][1]) if len(scored) > 1 else None

        # Nenhum candidato acima do limiar mínimo -> desconhecido.
        if best_sim < self.similarity_threshold:
            return IdentificationResult(
                status=RecognitionStatus.UNKNOWN,
                similarity_score=best_sim,
                confidence_score=0.0,
                runner_up=runner,
                **base,
            )

        confidence = self._confidence(best_sim, runner.similarity if runner else None)

        # Ambiguidade: 2º colocado também acima do limiar e dentro da margem.
        is_ambiguous = (
            runner is not None
            and runner.similarity >= self.similarity_threshold
            and (best_sim - runner.similarity) < self.ambiguity_margin
        )
        if is_ambiguous:
            return IdentificationResult(
                status=RecognitionStatus.AMBIGUOUS,
                employee_code=None,  # não escolhe automaticamente
                similarity_score=best_sim,
                confidence_score=confidence,
                runner_up=runner,
                requires_review=True,
                **base,
            )

        if confidence >= self.confidence_threshold:
            status = RecognitionStatus.MATCHED
            requires_review = False
        else:
            status = RecognitionStatus.LOW_CONFIDENCE
            requires_review = True

        return IdentificationResult(
            status=status,
            employee_code=best_code,
            similarity_score=best_sim,
            confidence_score=confidence,
            runner_up=runner,
            requires_review=requires_review,
            **base,
        )

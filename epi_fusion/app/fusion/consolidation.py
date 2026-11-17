"""
Consolidação de evidências por EPI entre câmeras.

Regras-chave:
- o silêncio de uma câmera é reinterpretado pelo perfil de visibilidade:
  câmera que NÃO vê a região -> NOT_VISIBLE (nunca MISSING);
- presença (ver o EPI) prevalece sobre ausência de quem não vê;
- confiança combinada por "noisy-OR" ponderado (não média simples): várias
  câmeras concordando elevam a confiança;
- conflito (ex.: PROPER x IMPROPER, ou presença x MISSING de câmeras que veem)
  é resolvido por visibilidade > confiança > recência; se não der para resolver
  com margem segura -> UNKNOWN e o conflito é registrado.

Importante: aqui é EVIDÊNCIA, não conformidade final (isso é do Módulo 3/regras).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import (
    NON_INFORMATIVE,
    PRESENCE_STATUSES,
    PPEStatus,
    PPEType,
)
from app.domain.models import (
    ConsolidatedPPE,
    Observation,
    PPEEvidence,
)


@dataclass(frozen=True)
class Contribution:
    camera_id: str
    status: PPEStatus
    confidence: float
    timestamp: datetime
    can_see: bool


def _noisy_or(confidences: list[float]) -> float:
    prod = 1.0
    for c in confidences:
        prod *= (1.0 - max(0.0, min(1.0, c)))
    return 1.0 - prod


class ConflictUnresolved(Exception):
    def __init__(self, contributions: list[Contribution]):
        self.contributions = contributions


class Consolidator:
    def __init__(self, conflict_margin: float) -> None:
        self._margin = conflict_margin

    # --- reinterpretação do silêncio pela visibilidade ---
    def effective(self, ppe: PPEType, obs: Observation, can_see: bool) -> Contribution:
        ev = obs.ppe.get(ppe)
        if ev is not None:
            return Contribution(obs.camera_id, ev.status, ev.confidence, obs.timestamp, can_see)
        # silêncio: câmera que não enxerga a região -> NOT_VISIBLE; senão NOT_OBSERVED
        status = PPEStatus.NOT_VISIBLE if not can_see else PPEStatus.NOT_OBSERVED
        return Contribution(obs.camera_id, status, 0.3, obs.timestamp, can_see)

    # --- resolução de conflito ---
    def _resolve(self, conflicting: list[Contribution]) -> Contribution:
        # câmeras que veem a região têm prioridade; se houver, descarta as que não veem
        seeing = [c for c in conflicting if c.can_see]
        pool = seeing or conflicting
        ranked = sorted(pool, key=lambda c: (c.confidence, c.timestamp), reverse=True)
        top = ranked[0]
        runner = next((c for c in ranked[1:] if c.status != top.status), None)
        if runner is not None and (top.confidence - runner.confidence) < self._margin:
            raise ConflictUnresolved(pool)  # dois resultados diferentes e críveis
        return top

    def consolidate(self, ppe: PPEType, contribs: list[Contribution]) -> tuple[ConsolidatedPPE, dict | None]:
        positives = [c for c in contribs if c.status in PRESENCE_STATUSES]
        missing = [c for c in contribs if c.status == PPEStatus.MISSING]
        cams_all = tuple(sorted({c.camera_id for c in contribs}))

        if positives:
            proper_like = [c for c in positives if c.status != PPEStatus.IMPROPER]
            improper = [c for c in positives if c.status == PPEStatus.IMPROPER]

            # conflito de CORRETUDE (present-and-proper x present-but-improper)
            if proper_like and improper:
                try:
                    winner = self._resolve(positives)
                    status = winner.status
                    conf = winner.confidence
                except ConflictUnresolved as exc:
                    return (
                        ConsolidatedPPE(PPEStatus.UNKNOWN, 0.5, cams_all, conflict=True),
                        self._conflict_payload(ppe, exc.contributions, "unresolved_proper_vs_improper"),
                    )
            else:
                status = PPEStatus.PROPER if any(c.status == PPEStatus.PROPER for c in positives) else PPEStatus.DETECTED
                conf = _noisy_or([c.confidence for c in positives])

            # conflito PRESENÇA x MISSING (só se a câmera que diz MISSING enxerga)
            credible_missing = [c for c in missing if c.can_see]
            if credible_missing:
                try:
                    winner = self._resolve(positives + credible_missing)
                    if winner.status == PPEStatus.MISSING:
                        return (ConsolidatedPPE(PPEStatus.MISSING, winner.confidence, cams_all, conflict=True),
                                self._conflict_payload(ppe, positives + credible_missing, "resolved_missing"))
                except ConflictUnresolved as exc:
                    return (
                        ConsolidatedPPE(PPEStatus.UNKNOWN, 0.5, cams_all, conflict=True),
                        self._conflict_payload(ppe, exc.contributions, "unresolved_presence_vs_missing"),
                    )

            return ConsolidatedPPE(status, conf, cams_all), None

        if missing:
            credible = [c for c in missing if c.can_see]
            if credible:
                return ConsolidatedPPE(PPEStatus.MISSING, _noisy_or([c.confidence for c in credible]), cams_all), None
            # ninguém que enxerga afirmou ausência -> não é MISSING
            return ConsolidatedPPE(PPEStatus.NOT_VISIBLE, 0.4, cams_all), None

        # só não-informativos
        statuses = {c.status for c in contribs}
        if statuses and statuses <= {PPEStatus.NOT_VISIBLE}:
            status = PPEStatus.NOT_VISIBLE
        elif PPEStatus.NOT_OBSERVED in statuses:
            status = PPEStatus.NOT_OBSERVED
        else:
            status = PPEStatus.UNKNOWN
        return ConsolidatedPPE(status, 0.3, cams_all), None

    @staticmethod
    def _conflict_payload(ppe: PPEType, contribs: list[Contribution], resolution: str) -> dict:
        return {
            "ppe_type": ppe,
            "resolution": resolution,
            "contributions": tuple(
                {"camera_id": c.camera_id, "status": c.status.value,
                 "confidence": round(c.confidence, 4), "can_see": c.can_see,
                 "timestamp": c.timestamp.isoformat()}
                for c in contribs
            ),
        }

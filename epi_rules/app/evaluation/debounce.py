"""
Debounce temporal + histerese.

Evita que um único frame gere violação definitiva e evita oscilação
(MISSING/DETECTED alternando). Mantém, por (employee_id, rule_id, ppe_type):
- desde quando a condição atual (violação ou conformidade) persiste;
- o estado estável atual (RuleState).

Uma violação só é CONFIRMADA após `min_violation_seconds` contínuos; uma
recuperação só é confirmada após `min_recovery_seconds` contínuos de
conformidade. Assim o Rules Engine emite transições significativas, não ruído.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import RequirementResult, RuleState
from app.infrastructure.clock import Clock


@dataclass
class _Track:
    state: RuleState
    condition_since: datetime  # início da condição instantânea atual
    last_instant: RequirementResult


class DebounceTracker:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._tracks: dict[tuple[str, str, str], _Track] = {}

    def update(
        self,
        key: tuple[str, str, str],
        instant: RequirementResult,
        min_violation_seconds: float,
        min_recovery_seconds: float,
    ) -> tuple[RuleState, bool, bool]:
        """
        Retorna (estado_estável, tornou_se_violacao, tornou_se_resolvido).
        `instant` é o resultado do frame atual para aquele requisito.
        """
        now = self._clock.now()
        track = self._tracks.get(key)

        if track is None:
            state = RuleState.VIOLATION if (instant == RequirementResult.NON_COMPLIANT and min_violation_seconds <= 0) \
                else (RuleState.PENDING if instant == RequirementResult.NON_COMPLIANT else _stable_from(instant))
            self._tracks[key] = _Track(state=state, condition_since=now, last_instant=instant)
            became_violation = state == RuleState.VIOLATION
            return state, became_violation, False

        # Reinicia o cronômetro se a condição instantânea mudou de "classe".
        if _class(instant) != _class(track.last_instant):
            track.condition_since = now
        track.last_instant = instant
        elapsed = (now - track.condition_since).total_seconds()

        became_violation = became_resolved = False

        if instant == RequirementResult.NON_COMPLIANT:
            if track.state != RuleState.VIOLATION:
                if elapsed >= min_violation_seconds:
                    became_violation = track.state != RuleState.VIOLATION
                    track.state = RuleState.VIOLATION
                else:
                    track.state = RuleState.PENDING
        elif instant == RequirementResult.COMPLIANT:
            if track.state == RuleState.VIOLATION:
                if elapsed >= min_recovery_seconds:
                    track.state = RuleState.RESOLVED
                    became_resolved = True
                # senão continua VIOLATION (histerese)
            else:
                track.state = RuleState.COMPLIANT
        else:  # INDETERMINATE / NOT_APPLICABLE
            if track.state != RuleState.VIOLATION:  # não derruba violação confirmada
                track.state = RuleState.INDETERMINATE if instant == RequirementResult.INDETERMINATE else RuleState.COMPLIANT

        return track.state, became_violation, became_resolved

    def reset(self) -> None:
        self._tracks.clear()


def _class(result: RequirementResult) -> str:
    if result == RequirementResult.NON_COMPLIANT:
        return "violation"
    if result == RequirementResult.COMPLIANT:
        return "ok"
    return "indeterminate"


def _stable_from(result: RequirementResult) -> RuleState:
    return {
        RequirementResult.COMPLIANT: RuleState.COMPLIANT,
        RequirementResult.INDETERMINATE: RuleState.INDETERMINATE,
        RequirementResult.NOT_APPLICABLE: RuleState.COMPLIANT,
    }.get(result, RuleState.INDETERMINATE)

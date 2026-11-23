"""
IncidentService — gestão do ciclo de vida da ocorrência (Fase 3.4).

Consome VIOLAÇÕES JÁ CONFIRMADAS pelo Rules Engine e decide APENAS como
registrar/deduplicar/encerrar a ocorrência. Não redecide conformidade, não
duplica debounce/histerese (confia nas transições do Rules Engine), não acessa
câmera/YOLO/fusão e não armazena dados biométricos.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.config import Settings
from app.domain.enums import (
    DETERMINED_STATUS,
    OPENING_STATUS,
    Action,
    EventType,
    IncidentStatus,
    OverallStatus,
    ReviewDecision,
    ViolationType,
)
from app.domain.models import EvaluationInput, Incident, ViolationInput, dedup_key
from app.infrastructure import Clock, EventBus, IncidentRepository
from app.observability import log_event, metrics


class IncidentError(Exception):
    pass


class InvalidViolation(IncidentError):
    pass


class IncidentNotFound(IncidentError):
    pass


class IncidentAlreadyResolved(IncidentError):
    pass


class InvalidReview(IncidentError):
    pass


class IncidentService:
    def __init__(self, settings: Settings, clock: Clock, event_bus: EventBus,
                 repository: IncidentRepository) -> None:
        self._s = settings
        self._clock = clock
        self._bus = event_bus
        self._repo = repository

    @property
    def repository(self) -> IncidentRepository:
        return self._repo

    @property
    def event_bus(self) -> EventBus:
        return self._bus

    def now(self) -> datetime:
        return self._clock.now()

    # ------------------------------------------------------------------ #
    # Abertura / atualização (VIOLATION_DETECTED)
    # ------------------------------------------------------------------ #
    def record_violation(self, v: ViolationInput) -> tuple[Incident, Action]:
        if not v.employee_id:
            raise InvalidViolation("employee_id é obrigatório para abrir incidente")
        if not v.ppe_type:
            raise InvalidViolation("ppe_type é obrigatório para abrir incidente")

        now = self._clock.now()
        existing = self._repo.open_by_key(v.key)

        if existing is None:
            return self._create(v, now), Action.CREATED

        # Deduplicação: já existe incidente ABERTO para a mesma violação lógica.
        self._merge_cameras(existing, v.source_cameras)

        # Idempotência: o mesmo evaluation_id não conta duas vezes.
        if v.evaluation_id and v.evaluation_id in existing._processed_eval_ids:
            return existing, Action.NOOP

        existing.occurrence_count += 1
        if v.evaluation_id:
            existing._processed_eval_ids.add(v.evaluation_id)
            existing.last_evaluation_id = v.evaluation_id
        existing.updated_at = now
        self._bus.publish(EventType.INCIDENT_UPDATED, self._payload(existing))
        log_event(EventType.INCIDENT_UPDATED, incident_id=existing.incident_id,
                  employee_id=existing.employee_id, ppe_type=existing.ppe_type,
                  occurrence_count=existing.occurrence_count)
        return existing, Action.UPDATED

    def _create(self, v: ViolationInput, now: datetime) -> Incident:
        inc = Incident(
            incident_id=self._repo.next_id(),
            employee_id=v.employee_id,
            rule_id=v.rule_id,
            rule_version=v.rule_version,
            ppe_type=v.ppe_type,
            violation_type=v.violation_type,
            reason_code=v.reason_code,
            reason=v.reason,
            severity=v.severity,           # severidade vem do Rules Engine (não recalcula)
            status=IncidentStatus.OPEN,
            opened_at=now,
            updated_at=now,
            first_evaluation_id=v.evaluation_id,
            last_evaluation_id=v.evaluation_id,
            occurrence_count=1,
            source_cameras=list(dict.fromkeys(v.source_cameras)),
            metadata=dict(v.metadata),
        )
        if v.evaluation_id:
            inc._processed_eval_ids.add(v.evaluation_id)
        self._repo.add(inc)
        metrics.record_created(inc.severity, inc.ppe_type)
        self._bus.publish(EventType.INCIDENT_CREATED, self._payload(inc))
        log_event(EventType.INCIDENT_CREATED, incident_id=inc.incident_id,
                  employee_id=inc.employee_id, ppe_type=inc.ppe_type,
                  reason_code=inc.reason_code, severity=inc.severity.value)
        return inc

    @staticmethod
    def _merge_cameras(inc: Incident, cameras) -> None:
        for cam in cameras:
            if cam and cam not in inc.source_cameras:
                inc.source_cameras.append(cam)

    # ------------------------------------------------------------------ #
    # Resolução (VIOLATION_RESOLVED)
    # ------------------------------------------------------------------ #
    def resolve_by_violation(self, employee_id: str, rule_id: str, ppe_type: str,
                             violation_type: ViolationType = ViolationType.PPE_VIOLATION) -> Optional[Incident]:
        key = dedup_key(employee_id, rule_id, ppe_type, violation_type.value)
        inc = self._repo.open_by_key(key)
        if inc is None:
            return None
        return self._resolve(inc)

    def resolve_incident(self, incident_id: str) -> Incident:
        inc = self._repo.get(incident_id)
        if inc is None:
            raise IncidentNotFound(incident_id)
        if inc.status == IncidentStatus.RESOLVED:
            raise IncidentAlreadyResolved(incident_id)
        return self._resolve(inc)

    def review_incident(self, incident_id: str, decision: str, note: str, reviewer: str) -> Incident:
        """Registra o parecer humano. Exige justificativa e identificação do revisor.
        Não muda OPEN/RESOLVED nem a conformidade. Cada revisão entra na trilha de auditoria."""
        inc = self._repo.get(incident_id)
        if inc is None:
            raise IncidentNotFound(incident_id)
        try:
            dec = ReviewDecision(str(decision).upper())
        except ValueError:
            raise InvalidReview(f"decisão inválida: {decision!r}. Use {[d.value for d in ReviewDecision]}")
        note = (note or "").strip()
        reviewer = (reviewer or "").strip()
        if len(note) < 3:
            raise InvalidReview("a justificativa é obrigatória")
        if not reviewer:
            raise InvalidReview("o revisor é obrigatório")
        now = self._clock.now()
        inc.review_status = dec.value
        inc.reviewed_by, inc.reviewed_at, inc.review_note = reviewer, now, note
        inc.updated_at = now
        inc.review_history.append({"decision": dec.value, "note": note, "reviewer": reviewer,
                                   "reviewed_at": now.isoformat()})
        self._bus.publish(EventType.INCIDENT_REVIEWED, {**self._payload(inc), "reviewer": reviewer})
        log_event(EventType.INCIDENT_REVIEWED, incident_id=inc.incident_id, decision=dec.value, reviewer=reviewer)
        return inc

    def _resolve(self, inc: Incident) -> Incident:
        now = self._clock.now()
        inc.status = IncidentStatus.RESOLVED
        inc.resolved_at = now
        inc.updated_at = now
        self._repo.mark_resolved_in_index(inc)
        metrics.record_resolved()
        self._bus.publish(EventType.INCIDENT_RESOLVED, {
            **self._payload(inc),
            "duration_seconds": round(inc.duration_seconds(now), 3),
        })
        log_event(EventType.INCIDENT_RESOLVED, incident_id=inc.incident_id,
                  employee_id=inc.employee_id, ppe_type=inc.ppe_type,
                  duration_seconds=round(inc.duration_seconds(now), 3))
        return inc

    # ------------------------------------------------------------------ #
    # Integração ponta-a-ponta com o Rules Engine
    # ------------------------------------------------------------------ #
    def process_evaluation(self, ev: EvaluationInput) -> list[tuple[Incident, Action]]:
        """Aplica uma ComplianceEvaluation inteira. Abre para cada violação
        confirmada e resolve o que deixou de estar em violação — respeitando o
        contrato: INDETERMINATE/NOT_EVALUATED não abrem nem encerram."""
        # NOT_EVALUATED ou sem funcionário -> nada (seção 11).
        if ev.employee_id is None or ev.overall_status == OverallStatus.NOT_EVALUATED:
            return []
        # Estados inconclusivos -> não abre nem resolve (seção 10).
        if ev.overall_status not in DETERMINED_STATUS:
            return []

        results: list[tuple[Incident, Action]] = []

        if ev.overall_status in OPENING_STATUS:  # NON_COMPLIANT
            current_keys = set()
            for v in ev.violations:
                inc, action = self.record_violation(v)
                results.append((inc, action))
                current_keys.add(v.key)
            # EPIs que tinham incidente aberto e não estão mais violados -> resolve.
            if ev.effective_rule_id:
                for open_inc in self._repo.open_for_employee_rule(ev.employee_id, ev.effective_rule_id):
                    if open_inc.key not in current_keys:
                        results.append((self._resolve(open_inc), Action.RESOLVED))

        elif ev.overall_status == OverallStatus.COMPLIANT:
            # Histerese: se o Rules Engine ainda lista a violação como confirmada
            # (a recuperação não durou `min_recovery_seconds`), o incidente
            # CONTINUA aberto. Só resolve o que deixou de estar na lista.
            still_violated = {v.key for v in ev.violations}
            if ev.effective_rule_id:
                for open_inc in self._repo.open_for_employee_rule(ev.employee_id, ev.effective_rule_id):
                    if open_inc.key in still_violated:
                        continue
                    results.append((self._resolve(open_inc), Action.RESOLVED))

        return results

    # ------------------------------------------------------------------ #
    # Consultas
    # ------------------------------------------------------------------ #
    def get(self, incident_id: str) -> Optional[Incident]:
        return self._repo.get(incident_id)

    def list(self, **filters) -> list[Incident]:
        return self._repo.filter(**filters)

    # ------------------------------------------------------------------ #
    def _payload(self, inc: Incident) -> dict:
        """Payload de evento — apenas dados estruturados, sem biometria."""
        return {
            "incident_id": inc.incident_id,
            "employee_id": inc.employee_id,
            "severity": inc.severity.value,
            "status": inc.status.value,
            "review_status": inc.review_status,
            "ppe_type": inc.ppe_type,
            "reason_code": inc.reason_code,
            "rule_id": inc.rule_id,
            "rule_version": inc.rule_version,
            "timestamp": inc.updated_at.isoformat(),
        }

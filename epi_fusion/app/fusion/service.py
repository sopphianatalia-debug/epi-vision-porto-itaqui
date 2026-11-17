"""
FusionService — consolida observações multi-câmera por employee_id.

Responsabilidades (seção 20 do spec) divididas em métodos coesos. Regras de
segurança centrais:
- só identidade MATCHED e válida vira chave de junção;
- observações sem chave viram ANÔNIMAS (nunca atribuídas por proximidade);
- person_track_id (por câmera) é sempre separado de employee_id;
- NOT_VISIBLE / NOT_OBSERVED nunca viram MISSING;
- NÃO decide conformidade final — apenas consolida evidência.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.config import Settings
from app.domain.enums import (
    NON_INFORMATIVE,
    PRESENCE_STATUSES,
    EventType,
    FusionStatus,
    IdentityStatus,
    PPEStatus,
    PPEType,
)
from app.domain.models import (
    AnonymousObservation,
    CameraContribution,
    CameraVisibilityProfile,
    ConsolidatedPPE,
    EmployeeSafetyState,
    FusionConflict,
    Observation,
)
from app.fusion.consolidation import Consolidator
from app.identity import IdentityResolution, IdentityResolver
from app.infrastructure import (
    AnonymousRepository,
    Clock,
    ConflictRepository,
    EventBus,
    ObservationRepository,
    StateRepository,
    VisibilityProfileRepository,
)
from app.observability import log_event, metrics


@dataclass(frozen=True)
class IngestResult:
    employee_id: Optional[str]
    identity_status: IdentityStatus
    kind: str  # "employee_state" | "anonymous"
    reason: str = ""


class ValidationError(Exception):
    pass


class FusionService:
    def __init__(
        self,
        settings: Settings,
        resolver: IdentityResolver,
        clock: Clock,
        event_bus: EventBus,
        observations: ObservationRepository,
        states: StateRepository,
        anonymous: AnonymousRepository,
        conflicts: ConflictRepository,
        visibility: VisibilityProfileRepository,
    ) -> None:
        self._s = settings
        self._resolver = resolver
        self._clock = clock
        self._bus = event_bus
        self._obs = observations
        self._states = states
        self._anon = anonymous
        self._conflicts = conflicts
        self._vis = visibility
        self._consolidator = Consolidator(settings.conflict_confidence_margin)
        self._required = [PPEType(p) for p in settings.required_ppe]
        # cache de last-known identity: (camera, track) -> (employee_id, ts)
        self._identity_cache: dict[tuple[str, str], tuple[str, datetime]] = {}

    # ------------------------------------------------------------------ #
    # 1. INGESTÃO
    # ------------------------------------------------------------------ #
    def ingest_observation(self, obs: Observation) -> IngestResult:
        start = time.perf_counter()
        self.validate_observation(obs)
        self._bus.publish(EventType.OBSERVATION_RECEIVED,
                          {"camera_id": obs.camera_id, "track_id": obs.person_track_id})
        log_event(EventType.OBSERVATION_RECEIVED, camera_id=obs.camera_id, track_id=obs.person_track_id)

        resolution = self.resolve_employee_key(obs)

        if resolution.is_joinable:
            result = self._ingest_identified(obs, resolution)
        else:
            result = self._ingest_anonymous(obs, resolution)

        latency_ms = (time.perf_counter() - start) * 1000.0
        # Sinais de observabilidade por câmera (não altera a fusão):
        # confidence média das evidências informativas e flag de NOT_VISIBLE.
        informative = [ev.confidence for ev in obs.ppe.values()
                       if ev.status in PRESENCE_STATUSES or ev.status == PPEStatus.MISSING]
        obs_confidence = (sum(informative) / len(informative)) if informative else None
        has_not_visible = any(ev.status == PPEStatus.NOT_VISIBLE for ev in obs.ppe.values())
        metrics.record_observation(
            obs.camera_id, latency_ms, result.kind == "employee_state", result.employee_id,
            confidence=obs_confidence, not_visible=has_not_visible,
        )
        metrics.set_active_states(len(self._states.all()))
        return result

    def validate_observation(self, obs: Observation) -> None:
        if not obs.camera_id or not obs.person_track_id:
            raise ValidationError("camera_id e person_track_id são obrigatórios")
        if not obs.observation_id:
            raise ValidationError("observation_id é obrigatório")
        for ppe, ev in obs.ppe.items():
            if not (0.0 <= ev.confidence <= 1.0):
                raise ValidationError(f"confidence inválida para {ppe.value}")

    # ------------------------------------------------------------------ #
    # 2. RESOLUÇÃO DA CHAVE (com last-known state)
    # ------------------------------------------------------------------ #
    def resolve_employee_key(self, obs: Observation) -> IdentityResolution:
        res = self._resolver.resolve(obs)
        key = (obs.camera_id, obs.person_track_id)
        now = self._clock.now()

        if res.is_joinable:
            self._identity_cache[key] = (res.employee_id, now)  # type: ignore[arg-type]
            log_event(EventType.IDENTITY_MATCHED, camera_id=obs.camera_id,
                      track_id=obs.person_track_id, employee_id=res.employee_id)
            return res

        # last-known: mantém identidade se o mesmo track foi identificado há pouco
        cached = self._identity_cache.get(key)
        if cached is not None:
            emp, ts = cached
            if (now - ts).total_seconds() <= self._s.identity_ttl_seconds:
                return IdentityResolution(emp, IdentityStatus.MATCHED, "last_known")
            del self._identity_cache[key]  # expirou

        if res.reason in ("invalid_employee_id", "inactive_employee_id"):
            log_event(EventType.INVALID_EMPLOYEE_ID, camera_id=obs.camera_id,
                      employee_id=obs.employee_id, reason=res.reason)
        else:
            log_event(EventType.IDENTITY_REJECTED, camera_id=obs.camera_id, reason=res.reason)
        return res

    # ------------------------------------------------------------------ #
    # 3. INGESTÃO IDENTIFICADA / ANÔNIMA
    # ------------------------------------------------------------------ #
    def _ingest_identified(self, obs: Observation, res: IdentityResolution) -> IngestResult:
        # Reescreve a observação com a chave resolvida (mantém o track original).
        resolved = Observation(
            observation_id=obs.observation_id,
            camera_id=obs.camera_id,
            timestamp=obs.timestamp,
            person_track_id=obs.person_track_id,
            identity_status=IdentityStatus.MATCHED,
            identity_confidence=obs.identity_confidence,
            ppe=obs.ppe,
            employee_id=res.employee_id,
        )
        existed = self._states.get(res.employee_id) is not None  # type: ignore[arg-type]
        self._obs.add(resolved)
        self.merge_observation(res.employee_id)  # type: ignore[arg-type]

        event = EventType.FUSION_UPDATED if existed else EventType.FUSION_CREATED
        self._bus.publish(event, {"employee_id": res.employee_id})
        log_event(event, employee_id=res.employee_id)
        return IngestResult(res.employee_id, IdentityStatus.MATCHED, "employee_state", res.reason)

    def _ingest_anonymous(self, obs: Observation, res: IdentityResolution) -> IngestResult:
        anon = AnonymousObservation(
            camera_id=obs.camera_id,
            person_track_id=obs.person_track_id,
            identity_status=res.identity_status,
            timestamp=obs.timestamp,
            ppe=obs.ppe,
        )
        self._anon.add(anon)
        self._bus.publish(EventType.ANONYMOUS_OBSERVATION,
                          {"camera_id": obs.camera_id, "track_id": obs.person_track_id})
        log_event(EventType.ANONYMOUS_OBSERVATION, camera_id=obs.camera_id,
                  track_id=obs.person_track_id, identity_status=res.identity_status.value)
        return IngestResult(None, res.identity_status, "anonymous", res.reason)

    # ------------------------------------------------------------------ #
    # 4. MERGE / CONSOLIDAÇÃO
    # ------------------------------------------------------------------ #
    def merge_observation(self, employee_id: str) -> Optional[EmployeeSafetyState]:
        now = self._clock.now()
        since = now - _seconds(self._s.fusion_window_seconds)
        latest = self._obs.latest_per_camera(employee_id, since)
        if not latest:
            return None

        ppe_consolidated: dict[PPEType, ConsolidatedPPE] = {}
        for ppe in PPEType:
            contribs = []
            for cam, o in latest.items():
                profile = self._vis.get(cam)
                can_see = profile.can_see(ppe) if profile else True
                contribs.append(self._consolidator.effective(ppe, o, can_see))
            consolidated, conflict = self._consolidator.consolidate(ppe, contribs)
            ppe_consolidated[ppe] = consolidated
            if conflict is not None:
                self._register_conflict(employee_id, conflict, now)

        cameras = {
            cam: CameraContribution(
                track_id=o.person_track_id,
                last_seen=o.timestamp,
                visible=[p for p, e in o.ppe.items() if e.status in PRESENCE_STATUSES],
            )
            for cam, o in latest.items()
        }
        overall, confidence = self._overall(ppe_consolidated)
        last_seen = max(o.timestamp for o in latest.values())

        state = EmployeeSafetyState(
            employee_id=employee_id,
            identity_status=IdentityStatus.MATCHED,
            last_seen=last_seen,
            cameras=cameras,
            ppe=ppe_consolidated,
            overall_status=overall,
            confidence=confidence,
        )
        self._states.put(state)
        return state

    def _overall(self, ppe: dict[PPEType, ConsolidatedPPE]) -> tuple[FusionStatus, float]:
        detected = missing = informative_conf = 0
        conf_sum = 0.0
        any_conflict = False
        for req in self._required:
            cp = ppe[req]
            if cp.conflict:
                any_conflict = True
            if cp.status in PRESENCE_STATUSES:
                detected += 1
                conf_sum += cp.confidence
                informative_conf += 1
            elif cp.status == PPEStatus.MISSING:
                missing += 1
                conf_sum += cp.confidence
                informative_conf += 1
        confidence = conf_sum / informative_conf if informative_conf else 0.0

        if any_conflict:
            return FusionStatus.CONFLICTING, confidence
        if detected == len(self._required):
            return FusionStatus.COMPLETE, confidence
        if detected > 0:
            return FusionStatus.PARTIAL, confidence
        return FusionStatus.INSUFFICIENT, confidence

    def _register_conflict(self, employee_id: str, payload: dict, now: datetime) -> None:
        conflict = FusionConflict(
            conflict_id=f"CONF-{uuid.uuid4().hex[:12]}",
            employee_id=employee_id,
            ppe_type=payload["ppe_type"],
            timestamp=now,
            contributions=payload["contributions"],
            resolved=payload["resolution"].startswith("resolved"),
            resolution=payload["resolution"],
        )
        self._conflicts.add(conflict)
        conflict_cameras = {c["camera_id"] for c in payload["contributions"] if c.get("camera_id")}
        metrics.record_conflict(conflict_cameras)
        self._bus.publish(EventType.FUSION_CONFLICT,
                          {"employee_id": employee_id, "ppe_type": conflict.ppe_type.value})
        log_event(EventType.FUSION_CONFLICT, employee_id=employee_id,
                  ppe_type=conflict.ppe_type.value, resolution=conflict.resolution)

    # ------------------------------------------------------------------ #
    # 5. CONSULTAS
    # ------------------------------------------------------------------ #
    def get_employee_state(self, employee_id: str) -> Optional[EmployeeSafetyState]:
        return self._states.get(employee_id)

    def get_all_states(self) -> list[EmployeeSafetyState]:
        return self._states.all()

    def get_recent_observations(self, employee_id: str) -> list[Observation]:
        since = self._clock.now() - _seconds(self._s.fusion_window_seconds)
        return self._obs.recent_for_employee(employee_id, since)

    def get_camera_state(self, camera_id: str) -> list[Observation]:
        return self._obs.for_camera(camera_id)

    def get_anonymous_observations(self, limit: int = 50) -> list[AnonymousObservation]:
        return self._anon.recent(limit)

    def get_conflicts(self, limit: int = 50) -> list[FusionConflict]:
        return self._conflicts.recent(limit)

    # ------------------------------------------------------------------ #
    # 6. VISIBILIDADE / EXPIRAÇÃO / RESET
    # ------------------------------------------------------------------ #
    def set_visibility_profile(self, profile: CameraVisibilityProfile) -> None:
        self._vis.put(profile)

    def get_visibility_profile(self, camera_id: str) -> Optional[CameraVisibilityProfile]:
        return self._vis.get(camera_id)

    def expire_stale_state(self) -> list[str]:
        now = self._clock.now()
        expired: list[str] = []
        for state in list(self._states.all()):
            if (now - state.last_seen).total_seconds() > self._s.state_ttl_seconds:
                self._states.remove(state.employee_id)
                expired.append(state.employee_id)
                self._bus.publish(EventType.STATE_EXPIRED, {"employee_id": state.employee_id})
                log_event(EventType.STATE_EXPIRED, employee_id=state.employee_id)
        if expired:
            metrics.record_expired(len(expired))
            metrics.set_active_states(len(self._states.all()))
        return expired

    def reset_state(self) -> None:
        for emp in list(self._states.all()):
            self._states.remove(emp.employee_id)
        self._identity_cache.clear()


def _seconds(value: float):
    from datetime import timedelta
    return timedelta(seconds=value)

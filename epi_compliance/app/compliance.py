"""
PPEComplianceService — orquestrador do Módulo 3.

Entrada: PersonObservation (um frame: pessoa rastreada + EPIs + contexto da
câmera). Saída: ComplianceResult com status por EPI (após análise temporal),
veredito geral e evidências quando há não conformidade.

É stateful por design: mantém a janela temporal por person_track_id entre
chamadas sucessivas do mesmo track.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.config import Settings
from app.enums import ComplianceStatus
from app.evaluators import evaluate_frame
from app.evidence import EvidenceService
from app.pose import build_pose_provider
from app.rules import ComplianceRulesEngine
from app.temporal import TemporalAggregator
from app.types import ComplianceResult, PersonObservation
from app.visibility import VisibilityAnalyzer


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PPEComplianceService:
    def __init__(
        self,
        settings: Settings,
        visibility: VisibilityAnalyzer,
        temporal: TemporalAggregator,
        rules: ComplianceRulesEngine,
        evidence: EvidenceService,
    ) -> None:
        self._s = settings
        self._visibility = visibility
        self._temporal = temporal
        self._rules = rules
        self._evidence = evidence
        self._pose = build_pose_provider(settings.pose_provider)
        self._last: dict[str, ComplianceResult] = {}

    @property
    def evidence(self) -> EvidenceService:
        return self._evidence

    def latest_states(self) -> list[dict]:
        return [r.to_dict() for r in self._last.values()]

    def evaluate(self, obs: PersonObservation) -> tuple[ComplianceResult, list[dict]]:
        regions = self._pose.regions(obs.person_bbox)
        vis = self._visibility.analyze(obs)
        frame_assessments = evaluate_frame(obs, regions, vis, self._s)

        # Agregação temporal por chave.
        agg = {
            key: self._temporal.push(obs.person_track_id, key, assessment)
            for key, assessment in frame_assessments.items()
        }

        result = ComplianceResult(
            person_track_id=obs.person_track_id,
            employee_id=obs.employee_id,
            camera_id=obs.camera_id,
            timestamp=_utc_iso(),
            helmet=agg["helmet"],
            vest=agg["vest"],
            glove_left=agg["glove_left"],
            glove_right=agg["glove_right"],
            glasses=agg["glasses"],
            boots=agg["boots"],
            overall=ComplianceStatus.UNDETERMINED,  # provisório
        )
        result.overall = self._rules.evaluate(result)

        evidence = self._evidence.maybe_capture(result, result.overall)
        self._last[obs.person_track_id] = result
        return result, evidence

    def reset_track(self, track_id: str) -> None:
        self._temporal.reset(track_id)
        self._last.pop(track_id, None)


def build_compliance_service(settings: Settings) -> PPEComplianceService:
    return PPEComplianceService(
        settings=settings,
        visibility=VisibilityAnalyzer(build_pose_provider(settings.pose_provider), settings.frame_edge_margin),
        temporal=TemporalAggregator(settings),
        rules=ComplianceRulesEngine(settings.required_ppe),
        evidence=EvidenceService(settings),
    )

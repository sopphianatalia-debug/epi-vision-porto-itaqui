"""
CameraObservationOrchestrator.

Recebe o resultado já processado de UMA câmera (detecção + tracking + associação
do Módulo 2, e identidade do Módulo 1), monta a Observation padronizada e a
encaminha ao FusionService. NÃO implementa regras de fusão (isso é do Fusion).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from app.domain.enums import IdentityStatus, PPEStatus, PPEType
from app.domain.models import Observation, PPEEvidence
from app.fusion.service import FusionService, IngestResult
from app.infrastructure import Clock


class CameraObservationOrchestrator:
    def __init__(self, fusion: FusionService, clock: Clock) -> None:
        self._fusion = fusion
        self._clock = clock

    def submit(
        self,
        camera_id: str,
        person_track_id: str,
        identity_status: str,
        identity_confidence: float,
        ppe: dict[str, dict],
        employee_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        observation_id: Optional[str] = None,
    ) -> IngestResult:
        obs = Observation(
            observation_id=observation_id or f"OBS-{uuid.uuid4().hex[:12]}",
            camera_id=camera_id,
            timestamp=timestamp or self._clock.now(),
            person_track_id=person_track_id,
            identity_status=IdentityStatus(identity_status),
            identity_confidence=identity_confidence,
            employee_id=employee_id,
            ppe={
                PPEType(k): PPEEvidence(PPEStatus(v["status"]), float(v.get("confidence", 0.0)))
                for k, v in ppe.items()
            },
        )
        return self._fusion.ingest_observation(obs)

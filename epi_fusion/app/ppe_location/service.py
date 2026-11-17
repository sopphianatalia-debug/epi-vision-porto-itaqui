"""
Evidência de LOCALIZAÇÃO de EPI (vinda do epi_tracker) — fonte separada.

Princípios (mesmos do módulo de tracker):
  * Tracker prova ONDE o EPI está; NÃO prova que alguém o está usando.
    ASSIGNED != WORN.
  * Esta evidência NÃO entra na consolidação por câmera (ConsolidatedPPE) e
    NÃO altera o estado de conformidade. Quem decide é o Rules Engine.
  * Divergência câmera x tracker é POSSIBLE_INCONSISTENCY — nunca violação.
  * Localização EXPIRED, ou evidência antiga demais, não afirma presença.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from app.domain.enums import PRESENCE_STATUSES, PPEType
from app.domain.models import EmployeeSafetyState

# Tipos do tracker que têm equivalente no vocabulário das câmeras.
_TRACKER_TO_CAMERA_TYPE = {"goggles": "glasses"}
_ASSERTING_STATES = {"CURRENT", "LAST_KNOWN"}


@dataclass(frozen=True)
class PPELocationEvidence:
    tracker_id: str
    ppe_id: Optional[str]
    ppe_type: Optional[str]
    employee_id_assigned: Optional[str]  # ASSIGNED, não WORN
    area_id: Optional[str]
    location_state: Optional[str]  # CURRENT | LAST_KNOWN | EXPIRED | ...
    confidence: Optional[float]
    source_timestamp: Optional[str]
    received_at: datetime

    def to_dict(self, *, stale: bool = False) -> dict:
        return {
            "source": "tracker",
            "tracker_id": self.tracker_id,
            "ppe_id": self.ppe_id,
            "ppe_type": self.ppe_type,
            "employee_id_assigned": self.employee_id_assigned,
            "area_id": self.area_id,
            "location_state": self.location_state,
            "confidence": self.confidence,
            "source_timestamp": self.source_timestamp,
            "received_at": self.received_at.isoformat(),
            "stale": stale,
            "proves_usage": False,
        }


class PPELocationService:
    def __init__(
        self,
        clock,
        state_lookup: Callable[[str], Optional[EmployeeSafetyState]],
        ttl_seconds: float = 30.0,
    ) -> None:
        self._clock = clock
        self._state_lookup = state_lookup
        self._ttl = ttl_seconds
        self._by_tracker: dict[str, PPELocationEvidence] = {}
        self._camera_area: dict[str, str] = {}

    # ---------------------------------------------------------------- #
    def ingest(self, payload: dict) -> PPELocationEvidence:
        tracker_id = payload.get("tracker_id")
        if not tracker_id:
            raise ValueError("tracker_id é obrigatório")
        confidence = payload.get("confidence")
        if confidence is not None and not (0.0 <= float(confidence) <= 1.0):
            raise ValueError("confidence inválida")
        ev = PPELocationEvidence(
            tracker_id=tracker_id,
            ppe_id=payload.get("ppe_id"),
            ppe_type=payload.get("ppe_type"),
            employee_id_assigned=payload.get("employee_id_assigned"),
            area_id=payload.get("area_id"),
            location_state=payload.get("location_state"),
            confidence=confidence,
            source_timestamp=payload.get("timestamp"),
            received_at=self._clock.now(),
        )
        self._by_tracker[tracker_id] = ev  # só a mais recente por tracker
        return ev

    def set_camera_area(self, camera_id: str, area_id: str) -> None:
        self._camera_area[camera_id] = area_id

    def get_camera_area(self, camera_id: str) -> Optional[str]:
        return self._camera_area.get(camera_id)

    def reset(self) -> None:
        self._by_tracker.clear()

    # ---------------------------------------------------------------- #
    def _is_stale(self, ev: PPELocationEvidence) -> bool:
        return (self._clock.now() - ev.received_at).total_seconds() > self._ttl

    def evidence_for_employee(self, employee_id: str) -> list[PPELocationEvidence]:
        return [e for e in self._by_tracker.values() if e.employee_id_assigned == employee_id]

    def inconsistencies_for_employee(self, employee_id: str) -> list[dict]:
        state = self._state_lookup(employee_id)
        if state is None:
            return []
        out: list[dict] = []
        for ev in self.evidence_for_employee(employee_id):
            if ev.location_state not in _ASSERTING_STATES or not ev.area_id or self._is_stale(ev):
                continue  # localização expirada/antiga não afirma nada
            camera_type = _TRACKER_TO_CAMERA_TYPE.get(ev.ppe_type or "", ev.ppe_type)
            try:
                ppe_enum = PPEType(camera_type) if camera_type else None
            except ValueError:
                ppe_enum = None
            consolidated = state.ppe.get(ppe_enum) if ppe_enum else None
            # só compara quando a câmera de fato viu o EPI
            if consolidated is None or consolidated.status not in PRESENCE_STATUSES:
                continue
            for camera_id in consolidated.contributing_cameras:
                camera_area = self._camera_area.get(camera_id)
                if camera_area and camera_area != ev.area_id:
                    out.append({
                        "type": "POSSIBLE_INCONSISTENCY",
                        "employee_id": employee_id,
                        "ppe_id": ev.ppe_id,
                        "ppe_type": ev.ppe_type,
                        "tracker_id": ev.tracker_id,
                        "camera_id": camera_id,
                        "camera_area_id": camera_area,
                        "camera_status": consolidated.status.value,
                        "tracker_area_id": ev.area_id,
                        "tracker_location_state": ev.location_state,
                        "is_violation": False,
                        "message": (
                            "Possível inconsistência entre evidência visual e localização do EPI. "
                            "Não indica, por si só, violação."
                        ),
                    })
        return out

    def employee_view(self, employee_id: str) -> dict:
        evidence = self.evidence_for_employee(employee_id)
        return {
            "employee_id": employee_id,
            "ppe_locations": [e.to_dict(stale=self._is_stale(e)) for e in evidence],
            "inconsistencies": self.inconsistencies_for_employee(employee_id),
            "note": "Localização do EPI não prova uso (ASSIGNED != WORN).",
        }

    def all_inconsistencies(self) -> list[dict]:
        employees = {e.employee_id_assigned for e in self._by_tracker.values() if e.employee_id_assigned}
        result: list[dict] = []
        for emp in sorted(employees):
            result.extend(self.inconsistencies_for_employee(emp))
        return result

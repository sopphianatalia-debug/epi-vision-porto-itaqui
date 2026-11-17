"""Entidades e value objects do domínio de fusão (fortemente tipados)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.enums import (
    PPE_REGION,
    BodyRegionKey,
    FusionStatus,
    IdentityStatus,
    PPEStatus,
    PPEType,
)


@dataclass(frozen=True)
class PPEEvidence:
    """Evidência de um EPI vinda de UMA câmera."""

    status: PPEStatus
    confidence: float


@dataclass(frozen=True)
class Observation:
    """Observação padronizada emitida por uma câmera (após detecção+identidade)."""

    observation_id: str
    camera_id: str
    timestamp: datetime
    person_track_id: str
    identity_status: IdentityStatus
    identity_confidence: float
    ppe: dict[PPEType, PPEEvidence]
    employee_id: Optional[str] = None


@dataclass(frozen=True)
class CameraVisibilityProfile:
    """O que cada câmera CONSEGUE observar (evita falsos MISSING)."""

    camera_id: str
    visibility: dict[BodyRegionKey, bool]

    def can_see(self, ppe: PPEType) -> bool:
        return self.visibility.get(PPE_REGION[ppe], False)


@dataclass(frozen=True)
class ConsolidatedPPE:
    status: PPEStatus
    confidence: float
    contributing_cameras: tuple[str, ...] = ()
    conflict: bool = False

    def to_dict(self) -> dict:
        d = {"status": self.status.value, "confidence": round(self.confidence, 4)}
        if self.contributing_cameras:
            d["cameras"] = list(self.contributing_cameras)
        if self.conflict:
            d["conflict"] = True
        return d


@dataclass
class CameraContribution:
    track_id: str
    last_seen: datetime
    visible: list[PPEType] = field(default_factory=list)


@dataclass
class EmployeeSafetyState:
    employee_id: str
    identity_status: IdentityStatus
    last_seen: datetime
    cameras: dict[str, CameraContribution]
    ppe: dict[PPEType, ConsolidatedPPE]
    overall_status: FusionStatus
    confidence: float

    def to_dict(self) -> dict:
        return {
            "employee_id": self.employee_id,
            "identity_status": self.identity_status.value,
            "last_seen": self.last_seen.isoformat(),
            "observations": {
                cam: {
                    "track_id": c.track_id,
                    "last_seen": c.last_seen.isoformat(),
                    "visible": [p.value for p in c.visible],
                }
                for cam, c in self.cameras.items()
            },
            "ppe": {p.value: cp.to_dict() for p, cp in self.ppe.items()},
            "overall_status": self.overall_status.value,
            "confidence": round(self.confidence, 4),
        }


@dataclass(frozen=True)
class AnonymousObservation:
    """Observação sem employee_id confiável — NUNCA atribuída a um funcionário."""

    camera_id: str
    person_track_id: str
    identity_status: IdentityStatus
    timestamp: datetime
    ppe: dict[PPEType, PPEEvidence]
    employee_id: None = None

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "person_track_id": self.person_track_id,
            "employee_id": None,
            "identity_status": self.identity_status.value,
            "timestamp": self.timestamp.isoformat(),
            "ppe": {p.value: {"status": e.status.value, "confidence": round(e.confidence, 4)}
                    for p, e in self.ppe.items()},
        }


@dataclass(frozen=True)
class FusionConflict:
    conflict_id: str
    employee_id: str
    ppe_type: PPEType
    timestamp: datetime
    contributions: tuple[dict, ...]
    resolved: bool
    resolution: str

    def to_dict(self) -> dict:
        return {
            "conflict_id": self.conflict_id,
            "employee_id": self.employee_id,
            "ppe_type": self.ppe_type.value,
            "timestamp": self.timestamp.isoformat(),
            "contributions": list(self.contributions),
            "resolved": self.resolved,
            "resolution": self.resolution,
        }

"""
Modelos de domínio do epi_tracker — Fase 3.8.

Dataclasses puras, sem dependência de framework (mesmo padrão dos outros
módulos: epi_incident/app/domain/models.py, epi_rules/app/domain/models.py).
Geração de ID e persistência ficam nos repositórios (infrastructure/), não
aqui.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.enums import (
    InconsistencyType,
    LocationState,
    ObservationStatus,
    PPEAssetStatus,
    PPEType,
    SafetyCheckStatus,
    TrackerStatus,
    TrackerTechnology,
)


class TrackerError(Exception):
    """Base para erros de domínio do módulo — convertidos em HTTP na camada de API."""


class UnknownTrackerError(TrackerError):
    pass


class TrackerAlreadyRegisteredError(TrackerError):
    pass


class CameraNotFoundError(TrackerError):
    pass


class CameraAlreadyRegisteredError(TrackerError):
    pass


@dataclass
class Camera:
    """Cadastro de uma câmera (administrativo): onde ela fica e que papel tem.
    `camera_id` é o MESMO que a câmera envia ao Fusion (--camera-id).
    Não decide conformidade; só descreve a câmera para a tela e para o mapa."""
    camera_id: str
    name: str
    sector: Optional[str] = None      # um dos códigos de domain/sectors.py (None = sem setor definido)
    kind: str = "INTERNA"             # ENTRADA (checkpoint) | INTERNA (movimentação)
    pos_x: float = 50.0               # posição no mapa esquemático, % (0-100)
    pos_y: float = 50.0
    active: bool = True
    example: bool = False             # câmera de exemplo/demonstração (não é câmera real)

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id, "name": self.name, "sector": self.sector, "kind": self.kind,
            "pos": {"x": self.pos_x, "y": self.pos_y}, "active": self.active, "example": self.example,
        }


@dataclass
class Tracker:
    tracker_id: str
    technology: TrackerTechnology
    registered_at: datetime
    status: TrackerStatus = TrackerStatus.ACTIVE
    battery_level: Optional[float] = None
    signal_strength: Optional[float] = None
    last_seen_at: Optional[datetime] = None
    last_area_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tracker_id": self.tracker_id,
            "technology": self.technology.value,
            "status": self.status.value,
            "battery_level": self.battery_level,
            "signal_strength": self.signal_strength,
            "registered_at": self.registered_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "last_area_id": self.last_area_id,
            "metadata": self.metadata,
        }


@dataclass
class PPEAsset:
    ppe_id: str
    ppe_type: PPEType
    registered_at: datetime
    tracker_id: Optional[str] = None
    employee_id: Optional[str] = None
    status: PPEAssetStatus = PPEAssetStatus.REGISTERED
    assigned_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ppe_id": self.ppe_id,
            "ppe_type": self.ppe_type.value,
            "tracker_id": self.tracker_id,
            "employee_id": self.employee_id,
            "status": self.status.value,
            "registered_at": self.registered_at.isoformat(),
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "metadata": self.metadata,
        }


@dataclass
class Area:
    area_id: str
    name: str
    type: str = "GENERIC"
    description: str = ""
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "area_id": self.area_id, "name": self.name, "type": self.type,
            "description": self.description, "active": self.active,
        }


@dataclass
class LocationReader:
    reader_id: str
    area_id: str
    technology: TrackerTechnology
    installed_at: datetime
    status: str = "ONLINE"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "reader_id": self.reader_id, "area_id": self.area_id,
            "technology": self.technology.value, "status": self.status,
            "installed_at": self.installed_at.isoformat(), "metadata": self.metadata,
        }


@dataclass
class SafetyCheckpoint:
    checkpoint_id: str
    area_id: str
    name: str
    camera_id: Optional[str] = None
    reader_id: Optional[str] = None
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "checkpoint_id": self.checkpoint_id, "area_id": self.area_id, "name": self.name,
            "camera_id": self.camera_id, "reader_id": self.reader_id, "active": self.active,
        }


@dataclass
class TrackerObservation:
    observation_id: str
    tracker_id: str
    reader_id: str
    area_id: str
    timestamp: datetime
    ppe_id: Optional[str] = None
    ppe_type: Optional[PPEType] = None
    employee_id: Optional[str] = None
    confidence: float = 1.0
    signal_strength: Optional[float] = None
    source: str = "mock"
    status: ObservationStatus = ObservationStatus.DETECTED
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "observation_id": self.observation_id, "tracker_id": self.tracker_id,
            "reader_id": self.reader_id, "area_id": self.area_id,
            "timestamp": self.timestamp.isoformat(),
            "ppe_id": self.ppe_id, "ppe_type": self.ppe_type.value if self.ppe_type else None,
            "employee_id": self.employee_id, "confidence": self.confidence,
            "signal_strength": self.signal_strength, "source": self.source,
            "status": self.status.value, "metadata": self.metadata,
        }


@dataclass
class SafetyCheck:
    check_id: str
    employee_id: Optional[str]
    area_id: str
    checkpoint_id: str
    timestamp: datetime
    status: SafetyCheckStatus
    camera_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    detected_ppe: list = field(default_factory=list)
    missing_ppe: list = field(default_factory=list)
    source: str = "camera"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id, "employee_id": self.employee_id, "area_id": self.area_id,
            "checkpoint_id": self.checkpoint_id, "camera_id": self.camera_id,
            "timestamp": self.timestamp.isoformat(), "evaluation_id": self.evaluation_id,
            "status": self.status.value, "detected_ppe": self.detected_ppe,
            "missing_ppe": self.missing_ppe, "source": self.source, "metadata": self.metadata,
        }


@dataclass
class LocationInconsistency:
    type: InconsistencyType
    employee_id: Optional[str]
    area_id: str
    ppe_id: str
    ppe_area_id: str
    timestamp: datetime

    def to_dict(self) -> dict:
        return {
            "type": self.type.value, "employee_id": self.employee_id, "area_id": self.area_id,
            "ppe_id": self.ppe_id, "ppe_area_id": self.ppe_area_id,
            "timestamp": self.timestamp.isoformat(),
        }


def location_state(observation: TrackerObservation, now: datetime, fresh_seconds: float,
                    ttl_seconds: float) -> LocationState:
    age = (now - observation.timestamp).total_seconds()
    if age > ttl_seconds:
        return LocationState.EXPIRED
    if age > fresh_seconds:
        return LocationState.LAST_KNOWN
    return LocationState.CURRENT

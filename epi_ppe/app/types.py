"""Estruturas de dados imutáveis do domínio de detecção."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.enums import DetectionClass


@dataclass(frozen=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def as_list(self) -> list[float]:
        return [self.x1, self.y1, self.x2, self.y2]


@dataclass(frozen=True)
class Detection:
    """Uma detecção crua do modelo: classe + confiança + caixa."""

    cls: DetectionClass
    confidence: float
    bbox: BoundingBox


@dataclass(frozen=True)
class PPEDetection:
    """Um EPI associado a uma pessoa, com o score de associação."""

    cls: DetectionClass
    confidence: float
    bbox: BoundingBox
    association_score: float


@dataclass
class PersonResult:
    """Resultado por pessoa: a pessoa rastreada + seus EPIs associados."""

    person_track_id: str
    person_bbox: BoundingBox
    person_confidence: float
    ppe: list[PPEDetection] = field(default_factory=list)
    employee_id: Optional[str] = None  # preenchido se integrado ao Módulo 1

    def to_dict(self, camera_id: str, timestamp: str) -> dict:
        return {
            "camera_id": camera_id,
            "timestamp": timestamp,
            "person_track_id": self.person_track_id,
            "employee_id": self.employee_id,
            "person": {
                "confidence": round(self.person_confidence, 4),
                "bbox": [round(v, 1) for v in self.person_bbox.as_list()],
            },
            "detections": [
                {
                    "type": d.cls.value,
                    "confidence": round(d.confidence, 4),
                    "bbox": [round(v, 1) for v in d.bbox.as_list()],
                    "association_score": round(d.association_score, 4),
                }
                for d in self.ppe
            ],
        }

    def to_module3_contract(self) -> dict:
        """
        Estrutura consumível pelo Módulo 3 (uso correto).
        Reporta apenas presença/ausência — NÃO decide se está sendo usado
        corretamente (isso é responsabilidade do Módulo 3).
        """
        present = {d.cls.value for d in self.ppe}
        from app.enums import PPE_CLASSES

        return {
            "person_track_id": self.person_track_id,
            "employee_id": self.employee_id,
            "ppe": {c.value: ("detected" if c in present else "not_detected") for c in PPE_CLASSES},
        }

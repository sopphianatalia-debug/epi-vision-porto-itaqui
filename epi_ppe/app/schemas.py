from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.enums import DetectionClass


class FrameRequest(BaseModel):
    camera_id: str = Field(examples=["CAM-07"])
    # Cena (provider mock/demo) — dict com "detections": [...]. Continua
    # exatamente como antes; nada muda para quem já usa mock/demo.
    frame: Optional[dict] = None
    # Imagem real (provider yolo), codificada em base64 (JPEG/PNG) — Fase
    # 3.7. Só um dos dois campos precisa vir preenchido; se os dois vierem,
    # frame_b64 tem prioridade. Ver app/api/routes.py::_decode_frame.
    frame_b64: Optional[str] = None


class DetectionOut(BaseModel):
    type: str
    confidence: float
    bbox: list[float]


class PersonResultOut(BaseModel):
    person_track_id: str
    employee_id: Optional[str] = None
    person_confidence: float
    person_bbox: list[float]
    detections: list[DetectionOut]


class ProcessFrameResponse(BaseModel):
    camera_id: str
    timestamp: str
    persons: list[PersonResultOut]


class RawDetectionResponse(BaseModel):
    camera_id: str
    model_version: str
    detections: list[DetectionOut]


class BoxIn(BaseModel):
    cls: DetectionClass
    bbox: list[float]
    confidence: float = 1.0


class EvaluateRequest(BaseModel):
    predictions: dict[str, list[BoxIn]]
    ground_truth: dict[str, list[BoxIn]]
    classes: Optional[list[DetectionClass]] = None


class ClassMetricsOut(BaseModel):
    cls: str
    precision: float
    recall: float
    f1: float
    ap: float
    tp: int
    fp: int
    fn: int


class EvaluateResponse(BaseModel):
    per_class: list[ClassMetricsOut]
    mAP: float
    iou_threshold: float

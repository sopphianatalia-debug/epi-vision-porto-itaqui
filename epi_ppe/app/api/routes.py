from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_pipeline
from app.config import get_settings
from app.enums import DetectionClass
from app.evaluation import evaluate
from app.observability.metrics import metrics
from app.pipeline import PPEPipeline
from app.schemas import (
    ClassMetricsOut,
    DetectionOut,
    EvaluateRequest,
    EvaluateResponse,
    FrameRequest,
    PersonResultOut,
    ProcessFrameResponse,
    RawDetectionResponse,
)
from app.types import BoundingBox, Detection

router = APIRouter()


def _decode_frame(body: FrameRequest) -> Any:
    """Fase 3.7 — resolve qual representação de frame usar.

    Import protegido (mesmo padrão do resto do módulo — OpenCVCamera,
    viewer/renderer.py): só exige `opencv-python-headless`/`numpy` quando
    `frame_b64` é realmente enviado. Quem usa só mock/demo (dict) nunca
    precisa dessas dependências, exatamente como antes desta fase.

    `frame_b64` é para o provider `yolo` (espera uma imagem de verdade,
    não um dict); `frame` continua sendo para mock/demo. Enviar frame_b64
    para um servidor configurado com provider mock resulta em erro — é uma
    combinação sem sentido, documentada no README da Fase 3.7 do
    epi_integration, não silenciosamente tolerada aqui.
    """
    if body.frame_b64 is not None:
        try:
            import base64
            import cv2  # type: ignore
            import numpy as np
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="frame_b64 requer `pip install opencv-python-headless numpy`.",
            ) from exc
        raw = base64.b64decode(body.frame_b64)
        arr = np.frombuffer(raw, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=422, detail="frame_b64 não pôde ser decodificado como imagem.")
        return image
    if body.frame is not None:
        return body.frame
    raise HTTPException(status_code=422, detail="Envie 'frame' (dict, mock/demo) ou 'frame_b64' (imagem, yolo).")


@router.get("/health", tags=["health"])
def health():
    s = get_settings()
    return {"status": "ok", "detector": s.detector_provider}


@router.get("/classes", tags=["config"])
def list_classes(pipeline: PPEPipeline = Depends(get_pipeline)):
    detector = pipeline._detector  # noqa: SLF001
    return {
        "classes": [c.value for c in DetectionClass],
        "thresholds": {c.value: detector.threshold_for(c) for c in DetectionClass},
        "model_version": detector.model_version,
    }


@router.post("/detect", response_model=RawDetectionResponse, tags=["detection"])
def detect(body: FrameRequest, pipeline: PPEPipeline = Depends(get_pipeline)):
    detector = pipeline._detector  # noqa: SLF001
    dets = detector.detect(_decode_frame(body))
    return RawDetectionResponse(
        camera_id=body.camera_id,
        model_version=detector.model_version,
        detections=[DetectionOut(type=d.cls.value, confidence=d.confidence, bbox=d.bbox.as_list()) for d in dets],
    )


@router.post("/pipeline/process-frame", response_model=ProcessFrameResponse, tags=["pipeline"])
def process_frame(body: FrameRequest, pipeline: PPEPipeline = Depends(get_pipeline)):
    results = pipeline.process_frame(body.camera_id, _decode_frame(body))
    persons = [
        PersonResultOut(
            person_track_id=r.person_track_id,
            employee_id=r.employee_id,
            person_confidence=round(r.person_confidence, 4),
            person_bbox=[round(v, 1) for v in r.person_bbox.as_list()],
            detections=[
                DetectionOut(type=d.cls.value, confidence=round(d.confidence, 4), bbox=d.bbox.as_list())
                for d in r.ppe
            ],
        )
        for r in results
    ]
    return ProcessFrameResponse(
        camera_id=body.camera_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        persons=persons,
    )


@router.get("/events", tags=["pipeline"])
def recent_events(limit: int = 50, pipeline: PPEPipeline = Depends(get_pipeline)):
    return pipeline.events.recent(limit)


@router.get("/metrics", tags=["observability"])
def performance_metrics():
    return metrics.snapshot()


@router.post("/evaluate", response_model=EvaluateResponse, tags=["evaluation"])
def evaluate_model(body: EvaluateRequest):
    s = get_settings()

    def to_dets(items) -> list[Detection]:
        return [Detection(cls=b.cls, confidence=b.confidence, bbox=BoundingBox(*b.bbox)) for b in items]

    preds = {img: to_dets(items) for img, items in body.predictions.items()}
    gts = {img: to_dets(items) for img, items in body.ground_truth.items()}
    classes = body.classes or list(DetectionClass)

    per_class, mean_ap = evaluate(preds, gts, classes, iou_thr=s.eval_iou_threshold)
    return EvaluateResponse(
        per_class=[
            ClassMetricsOut(
                cls=m.cls.value, precision=round(m.precision, 4), recall=round(m.recall, 4),
                f1=round(m.f1, 4), ap=round(m.ap, 4), tp=m.tp, fp=m.fp, fn=m.fn,
            )
            for m in per_class.values()
        ],
        mAP=round(mean_ap, 4),
        iou_threshold=s.eval_iou_threshold,
    )

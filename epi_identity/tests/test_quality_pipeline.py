import pytest

from app.config import Settings
from app.enums import RecognitionStatus
from app.recognition import build_recognition_service
from app.recognition.service import QualityTooLowError


def service(**overrides):
    s = Settings(face_provider="mock", quality_threshold=0.6, confidence_threshold=0.5, **overrides)
    return build_recognition_service(s)


def frame(seed="FUNC-1", quality=0.9, single=True, visible=True):
    return {"faces": [{"bbox": [0, 0, 100, 100], "seed": seed, "quality": quality,
                       "single_face": single, "face_visible": visible}]}


def test_low_quality_returns_unavailable():
    svc = service()
    good = svc.generate_enrollment_embedding(frame(seed="FUNC-1", quality=0.95))
    # Rosto de baixa qualidade não deve ser identificado, mesmo com galeria válida.
    result = svc.identify(frame(seed="FUNC-1", quality=0.3), gallery=[("FUNC-1", good.vector)])
    assert result.status == RecognitionStatus.UNAVAILABLE


def test_multiple_faces_blocks_identification():
    svc = service()
    two_faces = {"faces": [
        {"bbox": [0, 0, 50, 50], "seed": "A", "quality": 0.95, "single_face": False},
        {"bbox": [60, 0, 110, 50], "seed": "B", "quality": 0.95, "single_face": False},
    ]}
    result = svc.identify(two_faces, gallery=[])
    assert result.status == RecognitionStatus.UNAVAILABLE


def test_no_face_returns_unavailable():
    svc = service()
    result = svc.identify({"faces": []}, gallery=[])
    assert result.status == RecognitionStatus.UNAVAILABLE


def test_enrollment_rejects_low_quality():
    svc = service()
    with pytest.raises(QualityTooLowError):
        svc.generate_enrollment_embedding(frame(quality=0.2))


def test_identify_matches_enrolled_face():
    svc = service()
    f = frame(seed="FUNC-000234", quality=0.95)
    emb = svc.generate_enrollment_embedding(f)
    result = svc.identify(f, gallery=[("FUNC-000234", emb.vector)])
    assert result.status == RecognitionStatus.MATCHED
    assert result.employee_code == "FUNC-000234"

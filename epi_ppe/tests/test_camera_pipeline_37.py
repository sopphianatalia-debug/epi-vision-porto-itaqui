"""
Testes da Fase 3.7 dentro do epi_ppe — decodificação de imagem real
(base64) e mapa de nomes de classe configurável. Usam `pytest.importorskip`
para o cv2 (mesmo padrão já usado em test_viewer.py) — quem não tiver
opencv instalado simplesmente pula estes testes, sem quebrar o resto da
suíte.
"""
import base64

import pytest
from fastapi import HTTPException

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from app.api.routes import _decode_frame  # noqa: E402
from app.config import Settings  # noqa: E402
from app.detection.factory import build_provider  # noqa: E402
from app.detection.providers.yolo_provider import DEFAULT_NAME_MAP  # noqa: E402
from app.enums import DetectionClass  # noqa: E402
from app.schemas import FrameRequest  # noqa: E402


def _make_jpeg_b64(width=100, height=100) -> str:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.rectangle(img, (10, 10), (width - 10, height - 10), (0, 255, 0), -1)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return base64.b64encode(buf.tobytes()).decode("ascii")


# --------------------------------------------------------------------- #
# _decode_frame — a peça nova desta fase
# --------------------------------------------------------------------- #
def test_decode_frame_prefers_dict_when_only_dict_given():
    req = FrameRequest(camera_id="CAM-01", frame={"detections": []})
    result = _decode_frame(req)
    assert result == {"detections": []}


def test_decode_frame_decodes_base64_into_real_image_array():
    b64 = _make_jpeg_b64(width=120, height=80)
    req = FrameRequest(camera_id="CAM-01", frame_b64=b64)
    result = _decode_frame(req)
    assert isinstance(result, np.ndarray)
    assert result.shape == (80, 120, 3)  # (height, width, channels) — convenção OpenCV
    assert result.dtype == np.uint8


def test_decode_frame_b64_takes_priority_over_dict_if_both_given():
    b64 = _make_jpeg_b64()
    req = FrameRequest(camera_id="CAM-01", frame={"detections": []}, frame_b64=b64)
    result = _decode_frame(req)
    assert isinstance(result, np.ndarray)  # não o dict


def test_decode_frame_requires_at_least_one_field():
    req = FrameRequest(camera_id="CAM-01")
    with pytest.raises(HTTPException) as exc_info:
        _decode_frame(req)
    assert exc_info.value.status_code == 422


def test_decode_frame_invalid_base64_image_returns_422():
    garbage = base64.b64encode(b"isso nao e uma imagem valida").decode("ascii")
    req = FrameRequest(camera_id="CAM-01", frame_b64=garbage)
    with pytest.raises(HTTPException) as exc_info:
        _decode_frame(req)
    assert exc_info.value.status_code == 422


# --------------------------------------------------------------------- #
# Mapa de nomes de classe configurável (seção 2 da Fase 3.7)
# --------------------------------------------------------------------- #
def test_yolo_provider_uses_default_name_map_when_no_override():
    settings = Settings(detector_provider="yolo", detector_model_path="yolov8n.pt")
    provider = build_provider(settings)
    assert provider._name_map == DEFAULT_NAME_MAP  # noqa: SLF001


def test_yolo_provider_merges_custom_name_map_over_default():
    settings = Settings(
        detector_provider="yolo", detector_model_path="yolov8n.pt",
        detector_name_map_json='{"hard-hat": "HELMET", "no-vest": "SAFETY_VEST"}',
    )
    provider = build_provider(settings)
    assert provider._name_map["hard-hat"] == DetectionClass.HELMET  # noqa: SLF001
    assert provider._name_map["no-vest"] == DetectionClass.SAFETY_VEST  # noqa: SLF001
    # O resto do default continua presente — não foi substituído, foi mesclado.
    assert provider._name_map["helmet"] == DetectionClass.HELMET  # noqa: SLF001
    assert provider._name_map["person"] == DetectionClass.PERSON  # noqa: SLF001


def test_yolo_provider_invalid_json_raises_clear_error():
    settings = Settings(
        detector_provider="yolo", detector_model_path="yolov8n.pt",
        detector_name_map_json="{isso nao e json valido}",
    )
    with pytest.raises(ValueError, match="PPE_DETECTOR_NAME_MAP_JSON"):
        build_provider(settings)


def test_mock_provider_unaffected_by_name_map_setting():
    """Regressão — o campo novo não pode afetar o provider mock."""
    settings = Settings(detector_provider="mock", detector_name_map_json='{"x": "HELMET"}')
    provider = build_provider(settings)
    assert provider.__class__.__name__ == "MockDetector"

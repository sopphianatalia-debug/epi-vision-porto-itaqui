import numpy as np
import pytest

from app.config import Settings
from app.pipeline import build_pipeline

cv2 = pytest.importorskip("cv2")  # pula se opencv não estiver instalado

from app.viewer import draw_results  # noqa: E402


def test_demo_provider_detects_person_with_ppe():
    pipe = build_pipeline(Settings(detector_provider="demo"))
    frame = np.full((600, 960, 3), 32, dtype=np.uint8)
    results = pipe.process_frame("CAM-VIEW", frame)
    assert len(results) == 1
    types = {d.cls.value for d in results[0].ppe}
    assert {"HELMET", "SAFETY_VEST", "SAFETY_BOOTS"} <= types


def test_renderer_draws_without_display():
    # cv2.rectangle/putText não exigem display; imshow sim (não usado aqui).
    pipe = build_pipeline(Settings(detector_provider="demo"))
    frame = np.full((600, 960, 3), 32, dtype=np.uint8)
    results = pipe.process_frame("CAM-VIEW", frame)
    original_sum = int(frame.sum())  # antes de desenhar
    annotated = draw_results(frame, results, fps=25.0)
    assert annotated.shape == frame.shape
    # o frame foi modificado (caixas desenhadas) -> difere do fundo liso original
    assert int(annotated.sum()) != original_sum


def test_demo_person_moves_over_time():
    pipe = build_pipeline(Settings(detector_provider="demo"))
    frame = np.full((600, 960, 3), 32, dtype=np.uint8)
    x_positions = []
    for _ in range(15):
        r = pipe.process_frame("CAM-VIEW", frame)
        x_positions.append(r[0].person_bbox.x1)
    assert len(set(round(x, 1) for x in x_positions)) > 1  # a posição varia

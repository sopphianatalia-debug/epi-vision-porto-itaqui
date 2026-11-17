from app.camera import TestCamera
from app.config import Settings
from app.pipeline import build_pipeline


def scene_full_ppe():
    return {"detections": [
        {"cls": "PERSON", "confidence": 0.95, "bbox": [100, 100, 300, 500]},
        {"cls": "HELMET", "confidence": 0.96, "bbox": [150, 110, 230, 160]},
        {"cls": "SAFETY_VEST", "confidence": 0.94, "bbox": [130, 230, 270, 380]},
        {"cls": "SAFETY_BOOTS", "confidence": 0.9, "bbox": [130, 470, 270, 500]},
    ]}


def test_pipeline_associates_and_tracks():
    pipe = build_pipeline(Settings(detector_provider="mock"))
    results = pipe.process_frame("CAM-07", scene_full_ppe())
    assert len(results) == 1
    r = results[0]
    assert r.person_track_id == "TRACK-000001"
    types = {d.cls.value for d in r.ppe}
    assert {"HELMET", "SAFETY_VEST", "SAFETY_BOOTS"} <= types


def test_pipeline_keeps_track_id_across_frames():
    pipe = build_pipeline(Settings(detector_provider="mock"))
    r1 = pipe.process_frame("CAM-07", scene_full_ppe())
    r2 = pipe.process_frame("CAM-07", scene_full_ppe())
    assert r1[0].person_track_id == r2[0].person_track_id


def test_pipeline_records_events():
    pipe = build_pipeline(Settings(detector_provider="mock"))
    pipe.process_frame("CAM-07", scene_full_ppe())
    events = pipe.events.recent()
    assert events and events[0]["camera_id"] == "CAM-07"
    assert events[0]["person_track_id"] == "TRACK-000001"


def test_stream_processing_via_test_camera():
    pipe = build_pipeline(Settings(detector_provider="mock"))
    cam = TestCamera("CAM-99", [scene_full_ppe(), scene_full_ppe(), scene_full_ppe()])
    frames = pipe.process_stream(cam)
    assert len(frames) == 3


def test_camera_skips_invalid_frames():
    # None no meio do stream é pulado sem quebrar.
    pipe = build_pipeline(Settings(detector_provider="mock"))
    cam = TestCamera("CAM-1", [scene_full_ppe(), None, scene_full_ppe()])
    frames = pipe.process_stream(cam)
    # 2 frames válidos processados (o None é ignorado, não encerra o stream).
    assert len(frames) == 2


def test_empty_scene_returns_no_persons():
    pipe = build_pipeline(Settings(detector_provider="mock"))
    results = pipe.process_frame("CAM-07", {"detections": []})
    assert results == []

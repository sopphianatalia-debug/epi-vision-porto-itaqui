from app.config import Settings
from app.detection import build_detection_service
from app.enums import DetectionClass


def build(**over):
    return build_detection_service(Settings(detector_provider="mock", **over))


def test_threshold_filters_low_confidence_person():
    svc = build(person_confidence_threshold=0.8)
    frame = {"detections": [
        {"cls": "PERSON", "confidence": 0.6, "bbox": [0, 0, 100, 200]},  # abaixo -> descartado
        {"cls": "PERSON", "confidence": 0.9, "bbox": [300, 0, 400, 200]},
    ]}
    dets = svc.detect(frame)
    assert len(dets) == 1
    assert dets[0].confidence == 0.9


def test_nms_removes_duplicate_boxes():
    svc = build(nms_iou_threshold=0.5, helmet_confidence_threshold=0.1)
    frame = {"detections": [
        {"cls": "HELMET", "confidence": 0.95, "bbox": [10, 10, 60, 60]},
        {"cls": "HELMET", "confidence": 0.80, "bbox": [12, 12, 62, 62]},  # sobreposto -> suprimido
    ]}
    dets = svc.detect(frame)
    assert len(dets) == 1
    assert dets[0].confidence == 0.95


def test_different_classes_not_suppressed():
    svc = build()
    frame = {"detections": [
        {"cls": "HELMET", "confidence": 0.9, "bbox": [10, 10, 60, 60]},
        {"cls": "SAFETY_GLASSES", "confidence": 0.9, "bbox": [12, 12, 62, 62]},
    ]}
    dets = svc.detect(frame)
    assert len(dets) == 2


def test_person_and_ppe_services_split_classes():
    from app.detection import PersonDetectionService, PPEDetectionService

    svc = build()
    frame = {"detections": [
        {"cls": "PERSON", "confidence": 0.9, "bbox": [0, 0, 100, 200]},
        {"cls": "HELMET", "confidence": 0.9, "bbox": [10, 10, 60, 60]},
    ]}
    assert len(PersonDetectionService(svc).detect(frame)) == 1
    ppe = PPEDetectionService(svc).detect(frame)
    assert len(ppe) == 1 and ppe[0].cls == DetectionClass.HELMET

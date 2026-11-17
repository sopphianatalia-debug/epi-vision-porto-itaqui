from app.enums import DetectionClass
from app.evaluation import evaluate
from app.types import BoundingBox, Detection


def d(cls, x1, y1, x2, y2, conf=0.9):
    return Detection(cls, conf, BoundingBox(x1, y1, x2, y2))


def test_perfect_detection_gives_full_metrics():
    gt = {"img1": [d(DetectionClass.HELMET, 10, 10, 60, 60)]}
    pred = {"img1": [d(DetectionClass.HELMET, 11, 11, 61, 61, conf=0.95)]}
    per_class, mean_ap = evaluate(pred, gt, [DetectionClass.HELMET], iou_thr=0.5)
    m = per_class[DetectionClass.HELMET]
    assert m.precision == 1.0 and m.recall == 1.0 and m.f1 == 1.0
    assert m.tp == 1 and m.fp == 0 and m.fn == 0
    assert mean_ap == 1.0


def test_false_positive_lowers_precision():
    gt = {"img1": [d(DetectionClass.HELMET, 10, 10, 60, 60)]}
    pred = {"img1": [
        d(DetectionClass.HELMET, 11, 11, 61, 61, conf=0.95),
        d(DetectionClass.HELMET, 500, 500, 560, 560, conf=0.9),  # falso positivo
    ]}
    per_class, _ = evaluate(pred, gt, [DetectionClass.HELMET])
    m = per_class[DetectionClass.HELMET]
    assert m.tp == 1 and m.fp == 1
    assert m.precision == 0.5 and m.recall == 1.0


def test_missed_detection_lowers_recall():
    gt = {"img1": [
        d(DetectionClass.SAFETY_VEST, 10, 10, 60, 120),
        d(DetectionClass.SAFETY_VEST, 200, 10, 260, 120),
    ]}
    pred = {"img1": [d(DetectionClass.SAFETY_VEST, 11, 11, 61, 121, conf=0.9)]}
    per_class, _ = evaluate(pred, gt, [DetectionClass.SAFETY_VEST])
    m = per_class[DetectionClass.SAFETY_VEST]
    assert m.tp == 1 and m.fn == 1
    assert m.recall == 0.5 and m.precision == 1.0


def test_map_averages_over_classes():
    gt = {"img": [d(DetectionClass.HELMET, 0, 0, 50, 50), d(DetectionClass.GLOVES, 100, 100, 150, 150)]}
    pred = {"img": [d(DetectionClass.HELMET, 1, 1, 51, 51)]}  # acerta helmet, perde gloves
    per_class, mean_ap = evaluate(pred, gt, [DetectionClass.HELMET, DetectionClass.GLOVES])
    assert per_class[DetectionClass.HELMET].ap == 1.0
    assert per_class[DetectionClass.GLOVES].ap == 0.0
    assert mean_ap == 0.5

"""
Avaliação de qualidade do modelo (seções 13 e 14 do spec).

Compara detecções vs. ground-truth via IoU e calcula, por classe:
Precision, Recall, F1 e AP (Average Precision, base do mAP). O mAP é a média
dos APs entre as classes.

Formato esperado (por imagem):
    predictions[img] = [Detection, ...]
    ground_truth[img] = [Detection, ...]   (confidence ignorada no GT)
"""
from __future__ import annotations

from dataclasses import dataclass

from app.enums import DetectionClass
from app.geometry import iou
from app.types import Detection


@dataclass
class ClassMetrics:
    cls: DetectionClass
    precision: float
    recall: float
    f1: float
    ap: float
    tp: int
    fp: int
    fn: int


def _match_image(preds: list[Detection], gts: list[Detection], iou_thr: float) -> list[tuple[float, bool]]:
    """
    Para uma imagem e uma classe, ordena predições por confiança e marca cada
    uma como TP (bool) casando com o GT de maior IoU ainda não usado.
    Retorna [(confidence, is_tp), ...].
    """
    preds_sorted = sorted(preds, key=lambda d: d.confidence, reverse=True)
    used = [False] * len(gts)
    out: list[tuple[float, bool]] = []
    for p in preds_sorted:
        best_iou, best_j = iou_thr, -1
        for j, g in enumerate(gts):
            if used[j]:
                continue
            score = iou(p.bbox, g.bbox)
            if score >= best_iou:
                best_iou, best_j = score, j
        if best_j >= 0:
            used[best_j] = True
            out.append((p.confidence, True))
        else:
            out.append((p.confidence, False))
    return out


def _average_precision(scored: list[tuple[float, bool]], total_gt: int) -> float:
    """AP por interpolação de todos os pontos (estilo COCO/VOC-2010)."""
    if total_gt == 0:
        return 0.0
    scored.sort(key=lambda t: t[0], reverse=True)
    tp = fp = 0
    precisions, recalls = [], []
    for _, is_tp in scored:
        if is_tp:
            tp += 1
        else:
            fp += 1
        precisions.append(tp / (tp + fp))
        recalls.append(tp / total_gt)
    # Envelope de precisão (monotônico decrescente) e integração por retângulos.
    ap, prev_recall = 0.0, 0.0
    for i in range(len(recalls)):
        max_prec = max(precisions[i:]) if precisions[i:] else 0.0
        ap += (recalls[i] - prev_recall) * max_prec
        prev_recall = recalls[i]
    return ap


def evaluate(
    predictions: dict[str, list[Detection]],
    ground_truth: dict[str, list[Detection]],
    classes: list[DetectionClass],
    iou_thr: float = 0.5,
) -> tuple[dict[DetectionClass, ClassMetrics], float]:
    per_class: dict[DetectionClass, ClassMetrics] = {}
    images = set(predictions) | set(ground_truth)

    for cls in classes:
        scored: list[tuple[float, bool]] = []
        total_gt = 0
        for img in images:
            preds = [d for d in predictions.get(img, []) if d.cls == cls]
            gts = [d for d in ground_truth.get(img, []) if d.cls == cls]
            total_gt += len(gts)
            scored.extend(_match_image(preds, gts, iou_thr))

        tp = sum(1 for _, is_tp in scored if is_tp)
        fp = sum(1 for _, is_tp in scored if not is_tp)
        fn = total_gt - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / total_gt if total_gt else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        ap = _average_precision(list(scored), total_gt)
        per_class[cls] = ClassMetrics(cls, precision, recall, f1, ap, tp, fp, fn)

    maps = [m.ap for m in per_class.values()]
    mean_ap = sum(maps) / len(maps) if maps else 0.0
    return per_class, mean_ap

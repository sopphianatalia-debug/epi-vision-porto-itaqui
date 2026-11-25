"""Recorte da pessoa para a evidência do incidente.

Só o recorte (com margem, corpo inteiro) sai do quadro — nunca o quadro inteiro. As caixas de detecção
são convertidas para coordenadas 0..1 RELATIVAS AO RECORTE; a tela desenha por cima da imagem intacta.
Nada de reconhecimento facial entra aqui.
"""
from __future__ import annotations

from typing import Any, Optional

MARGIN = 0.15          # margem ao redor da pessoa, para o corpo aparecer inteiro
MAX_SIDE = 1280        # mesmo limite do Incident Service
MIN_SIDE = 16


MIN_BRIGHTNESS = 45    # média de cinza (0..255) da pessoa abaixo da qual o quadro é escuro demais para servir de prova


def person_brightness(frame: Any, person_bbox) -> Optional[float]:
    """Brilho médio (0..255) da região da pessoa; None se não der para medir. Serve para não guardar como
    evidência o quadro escuro de uma webcam que ainda está ajustando a exposição."""
    shape = getattr(frame, "shape", None)
    if shape is None or len(shape) < 2 or not person_bbox or len(person_bbox) != 4:
        return None
    fh, fw = int(shape[0]), int(shape[1])
    x1, y1, x2, y2 = (int(max(0, v)) for v in person_bbox)
    x2, y2 = min(fw, x2), min(fh, y2)
    if x2 - x1 < MIN_SIDE or y2 - y1 < MIN_SIDE:
        return None
    return float(frame[y1:y2, x1:x2].mean())


def build_findings(ppe_payload: Optional[dict], visibility: Optional[dict] = None) -> list[dict]:
    """Resumo por EPI para o revisor. PRESENT/MISSING vêm do que o pipeline observou; um EPI sem observação
    cuja região do corpo está fora do enquadramento é NOT_VISIBLE (não ver != faltar). Sem posição inventada."""
    regions = {"helmet": "head", "vest": "torso", "gloves": "hands", "boots": "feet"}
    out = []
    for ppe, region in regions.items():
        item = (ppe_payload or {}).get(ppe)
        status = item.get("status") if isinstance(item, dict) else None
        if status == "MISSING":
            out.append({"label": ppe, "status": "MISSING"})
        elif status in ("DETECTED", "WORN"):
            out.append({"label": ppe, "status": "PRESENT"})
        elif status is None and visibility is not None and visibility.get(region) is False:
            out.append({"label": ppe, "status": "NOT_VISIBLE"})
    return out


def build_evidence(frame: Any, person_bbox, detections, ppe_status: Optional[dict] = None,
                   jpeg_quality: int = 85) -> Optional[tuple[bytes, list[dict]]]:
    """(jpeg, detecções normalizadas) ou None se não houver como recortar."""
    shape = getattr(frame, "shape", None)
    if shape is None or len(shape) < 2 or not person_bbox or len(person_bbox) != 4:
        return None
    import cv2  # type: ignore

    fh, fw = int(shape[0]), int(shape[1])
    x1, y1, x2, y2 = (float(v) for v in person_bbox)
    if x2 <= x1 or y2 <= y1:
        return None
    mx, my = (x2 - x1) * MARGIN, (y2 - y1) * MARGIN
    cx1, cy1 = max(0, int(x1 - mx)), max(0, int(y1 - my))
    cx2, cy2 = min(fw, int(x2 + mx) + 1), min(fh, int(y2 + my) + 1)
    cw, ch = cx2 - cx1, cy2 - cy1
    if cw < MIN_SIDE or ch < MIN_SIDE:
        return None
    crop = frame[cy1:cy2, cx1:cx2]
    scale = min(1.0, MAX_SIDE / max(cw, ch))
    if scale < 1.0:
        crop = cv2.resize(crop, (max(1, int(cw * scale)), max(1, int(ch * scale))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if not ok:
        return None

    px1, py1, px2, py2 = max(x1, cx1), max(y1, cy1), min(x2, cx2), min(y2, cy2)   # pessoa cortada pelo quadro: só a parte dentro do recorte
    out: list[dict] = [{"label": "person", "bbox": [round((px1 - cx1) / cw, 4), round((py1 - cy1) / ch, 4),
                                                      round((px2 - px1) / cw, 4), round((py2 - py1) / ch, 4)]}]
    for d in (detections or [])[:20]:
        b = d.get("bbox") or []
        label = d.get("type") or d.get("cls")
        if len(b) != 4 or not label:
            continue
        bx1, by1 = max(b[0], cx1), max(b[1], cy1)
        bx2, by2 = min(b[2], cx2), min(b[3], cy2)
        if bx2 <= bx1 or by2 <= by1:
            continue
        item = {"label": str(label).lower()[:40],
                "bbox": [round((bx1 - cx1) / cw, 4), round((by1 - cy1) / ch, 4),
                         round((bx2 - bx1) / cw, 4), round((by2 - by1) / ch, 4)]}
        if isinstance(d.get("confidence"), (int, float)):
            item["confidence"] = round(min(max(float(d["confidence"]), 0.0), 1.0), 4)
        st = (ppe_status or {}).get(item["label"])
        if isinstance(st, str):
            item["status"] = st[:20]
        out.append(item)
    return buf.tobytes(), out

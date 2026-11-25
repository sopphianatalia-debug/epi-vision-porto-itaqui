"""
Recorte do rosto (parte de cima da pessoa) para o reconhecimento facial opt-in.

A imagem existe só em memória: vira JPEG em base64, vai na requisição ao Identity e é descartada. Nada é gravado
em disco nem registrado em log. Se o recorte for pequeno demais para conter um rosto, devolve None e o pipeline
trata como "não identificado" (sem chamar o Identity).
"""
from __future__ import annotations

import base64
from typing import Any, Optional

UPPER_FRACTION = 0.45        # cabeça e ombros: topo da caixa da pessoa
MAX_SIDE_PX = 640
MIN_SIDE_PX = 64
JPEG_QUALITY = 90


def face_probe_b64(frame: Any, person_bbox) -> Optional[str]:
    shape = getattr(frame, "shape", None)
    if shape is None or len(shape) < 2 or not person_bbox or len(person_bbox) != 4:
        return None
    import cv2  # noqa: PLC0415
    h, w = shape[0], shape[1]
    x1, y1, x2, y2 = (float(v) for v in person_bbox)
    x1, x2 = max(0.0, min(x1, x2)), min(float(w), max(x1, x2))
    y1, y2 = max(0.0, min(y1, y2)), min(float(h), max(y1, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    y_end = y1 + (y2 - y1) * UPPER_FRACTION
    crop = frame[int(y1):int(y_end), int(x1):int(x2)]
    if crop.size == 0 or min(crop.shape[:2]) < MIN_SIDE_PX:
        return None
    ch, cw = crop.shape[:2]
    if max(ch, cw) > MAX_SIDE_PX:
        f = MAX_SIDE_PX / max(ch, cw)
        crop = cv2.resize(crop, (max(1, int(cw * f)), max(1, int(ch * f))), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return base64.b64encode(buf.tobytes()).decode() if ok else None

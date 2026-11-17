"""
Renderização das detecções sobre o frame (OpenCV).

Desenha a caixa da pessoa com seu track_id, as caixas dos EPIs com classe +
confiança, e um cabeçalho com FPS e contagens. Import de cv2 protegido.

As funções de desenho do OpenCV NÃO exigem display — só cv2.imshow exige.
Por isso o renderer funciona também em modo headless (salvando em arquivo).
"""
from __future__ import annotations

from typing import Any, Optional

from app.enums import DetectionClass
from app.types import PersonResult

# Cores BGR por classe (OpenCV usa BGR, não RGB).
CLASS_COLORS = {
    DetectionClass.PERSON: (255, 200, 0),        # azul-ciano
    DetectionClass.HELMET: (0, 215, 255),        # amarelo
    DetectionClass.SAFETY_VEST: (0, 165, 255),   # laranja
    DetectionClass.GLOVES: (255, 0, 200),        # magenta
    DetectionClass.SAFETY_BOOTS: (0, 255, 120),  # verde
    DetectionClass.SAFETY_GLASSES: (255, 255, 0),
    DetectionClass.EAR_PROTECTION: (200, 120, 255),
}
PERSON_COLOR = (60, 220, 60)

# Rótulos amigáveis (curtos) por classe.
SHORT_LABEL = {
    DetectionClass.HELMET: "Helmet",
    DetectionClass.SAFETY_VEST: "Vest",
    DetectionClass.GLOVES: "Gloves",
    DetectionClass.SAFETY_BOOTS: "Boots",
    DetectionClass.SAFETY_GLASSES: "Glasses",
    DetectionClass.EAR_PROTECTION: "Ear",
}


def _cv2():
    try:
        import cv2  # type: ignore
        return cv2
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Renderização requer `pip install opencv-python-headless`.") from exc


def _label(cv2, frame, text, x, y, color, scale=0.5):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), base = cv2.getTextSize(text, font, scale, 1)
    y_top = max(0, y - th - base - 2)
    cv2.rectangle(frame, (x, y_top), (x + tw + 4, y_top + th + base + 2), color, -1)
    cv2.putText(frame, text, (x + 2, y_top + th), font, scale, (20, 20, 20), 1, cv2.LINE_AA)


def draw_results(frame: Any, results: list[PersonResult], fps: Optional[float] = None) -> Any:
    cv2 = _cv2()
    out = frame

    for r in results:
        b = r.person_bbox
        p1, p2 = (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2))
        cv2.rectangle(out, p1, p2, PERSON_COLOR, 2)
        # "Pessoa #1" a partir do sufixo numérico do track id
        num = r.person_track_id.split("-")[-1].lstrip("0") or "0"
        _label(cv2, out, f"Pessoa #{num}  {r.person_track_id}", p1[0], p1[1], PERSON_COLOR, 0.55)

        for d in r.ppe:
            db = d.bbox
            c = CLASS_COLORS.get(d.cls, (255, 255, 255))
            cv2.rectangle(out, (int(db.x1), int(db.y1)), (int(db.x2), int(db.y2)), c, 2)
            name = SHORT_LABEL.get(d.cls, d.cls.value)
            _label(cv2, out, f"{name} {int(d.confidence * 100)}%", int(db.x1), int(db.y1), c, 0.45)

    # Cabeçalho com FPS + contagem de pessoas
    header = f"Pessoas: {len(results)}"
    if fps is not None:
        header = f"FPS: {fps:.1f}   " + header
    cv2.rectangle(out, (0, 0), (max(220, 12 * len(header)), 28), (30, 30, 30), -1)
    cv2.putText(out, header, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1, cv2.LINE_AA)
    return out

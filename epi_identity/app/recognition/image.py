"""
Imagem de rosto recebida pela API (frame real, não o "frame mock" dos testes).

Formato:  {"image_base64": "<JPEG ou PNG em base64>"}

A imagem existe só em memória durante a requisição: este módulo decodifica e valida, nada é gravado em
disco nem registrado em log. Validações (a API é chamada por outros serviços, mas não confiamos no conteúdo):
tamanho em bytes, assinatura do arquivo (JPEG/PNG), dimensões lidas do cabeçalho ANTES de decodificar
(evita imagem pequena em bytes mas gigante em pixels) e decodificação bem-sucedida.
"""
from __future__ import annotations

import base64
import binascii
import struct
from typing import Any

MAX_IMAGE_BYTES = 2_000_000          # decodificado
MAX_SIDE_PX = 1920
MAX_PIXELS = 4_000_000               # ~2000x2000
MIN_SIDE_PX = 32


class InvalidImageError(ValueError):
    """A imagem enviada não é utilizável (formato, tamanho ou conteúdo inválido)."""


def is_image_payload(frame: Any) -> bool:
    return isinstance(frame, dict) and "image_base64" in frame


def _dimensions(data: bytes) -> tuple[int, int]:
    """(largura, altura) lidas do cabeçalho de JPEG ou PNG, sem decodificar os pixels."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if len(data) < 24:
            raise InvalidImageError("PNG truncado.")
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        n = len(data)
        while i + 9 < n:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
                i += 1 if marker == 0xFF else 2
                continue
            seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + seg_len
        raise InvalidImageError("JPEG sem dimensões.")
    raise InvalidImageError("Formato não suportado (use JPEG ou PNG).")


def decode_image(frame: dict):
    """Decodifica o payload em um ndarray BGR (formato do OpenCV/InsightFace)."""
    raw = frame.get("image_base64") if isinstance(frame, dict) else None
    if not isinstance(raw, str) or not raw:
        raise InvalidImageError("Imagem ausente.")
    if len(raw) > MAX_IMAGE_BYTES * 4 // 3 + 16:
        raise InvalidImageError("Imagem grande demais.")
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidImageError("Base64 inválido.") from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise InvalidImageError("Imagem grande demais.")

    w, h = _dimensions(data)
    if min(w, h) < MIN_SIDE_PX:
        raise InvalidImageError("Imagem pequena demais.")
    if max(w, h) > MAX_SIDE_PX or w * h > MAX_PIXELS:
        raise InvalidImageError("Dimensões acima do limite.")

    import cv2  # type: ignore  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None or img.ndim != 3:
        raise InvalidImageError("Não foi possível decodificar a imagem.")
    return img

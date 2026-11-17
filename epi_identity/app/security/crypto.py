"""
Proteção criptográfica de templates biométricos.

Embeddings NUNCA são gravados em texto claro. Usamos Fernet (AES-128-CBC +
HMAC) como implementação de referência. Em produção, a chave deve ser
gerenciada por KMS/HSM e rotacionada; este módulo isola essa dependência.
"""
from __future__ import annotations

import struct
from functools import lru_cache
from typing import Sequence

from cryptography.fernet import Fernet

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.biometric_encryption_key
    if not key:
        # Chave efêmera apenas para dev/testes. Em prod é obrigatório configurar.
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_embedding(vector: Sequence[float]) -> bytes:
    """Serializa (float32) e criptografa o embedding."""
    packed = struct.pack(f"{len(vector)}f", *vector)
    return _fernet().encrypt(packed)


def decrypt_embedding(blob: bytes, dim: int) -> list[float]:
    """Descriptografa e desserializa para lista de floats."""
    packed = _fernet().decrypt(blob)
    return list(struct.unpack(f"{dim}f", packed))

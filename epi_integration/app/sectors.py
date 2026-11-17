"""Códigos de setor do Porto do Itaqui (contrato entre Spring, Identity e a tela Câmeras).

São os MESMOS códigos de `epi_tracker/frontend/src/config/itaqui.js` (SECTORS).
O setor de um trabalhador vem do cadastro (Spring); aqui só validamos o código.
EPIs exigidos por setor AINDA NÃO foram validados com especialista do porto.
"""
from __future__ import annotations

from typing import Optional

SECTOR_CODES: tuple[str, ...] = (
    "GRANEIS_SOLIDOS",
    "GRANEIS_LIQUIDOS",
    "CARGA_GERAL_CELULOSE",
    "PIER_BORDO",
    "MANUTENCAO_ENGENHARIA",
    "GUARDA_PORTUARIA",
)


def normalize_sector(value: object) -> Optional[str]:
    """Texto limpo em MAIÚSCULAS, ou None se vazio/ausente. Não valida."""
    if value is None:
        return None
    s = str(value).strip().upper()
    return s or None


def is_valid_sector(code: Optional[str]) -> bool:
    return code in SECTOR_CODES

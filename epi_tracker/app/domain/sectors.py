"""Setores do Porto do Itaqui e tipos de câmera (contrato com o Spring e a tela Câmeras).

Os 6 códigos são os MESMOS de epi_integration/app/sectors.py e do front (config/itaqui.js).
Há testes que impedem divergência.
"""
from __future__ import annotations

SECTOR_CODES: tuple[str, ...] = (
    "GRANEIS_SOLIDOS",
    "GRANEIS_LIQUIDOS",
    "CARGA_GERAL_CELULOSE",
    "PIER_BORDO",
    "MANUTENCAO_ENGENHARIA",
    "GUARDA_PORTUARIA",
)
CAMERA_KINDS: tuple[str, ...] = ("ENTRADA", "INTERNA")

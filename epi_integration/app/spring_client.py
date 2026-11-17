"""Cliente do backend Spring Boot do grupo (cadastro administrativo).

Só LEITURA: este lado nunca grava no Spring. O Spring é a fonte do cadastro
(trabalhadores, treinamentos); o lado Python só consome.

Contrato atual do Spring (branch feature/fastapi-vision):
  GET /api/trabalhadores -> [{id (UUID), nome, matricula, empresa, ativo,
                              setor (opcional), cargo (opcional)}]
`setor` deve ser um dos códigos de app/sectors.py; ausente é aceito.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from app.sectors import normalize_sector


@dataclass(frozen=True)
class Trabalhador:
    id: str
    nome: str
    matricula: str
    empresa: str
    ativo: bool
    setor: Optional[str] = None   # código de setor (app/sectors.py); None = o Spring não informou
    cargo: Optional[str] = None

    @staticmethod
    def from_json(d: dict) -> "Trabalhador":
        return Trabalhador(
            id=str(d["id"]),
            nome=str(d["nome"]),
            matricula=str(d["matricula"]),
            empresa=str(d.get("empresa") or ""),
            # ausente => ativo: o Spring grava ativo=true por padrão.
            ativo=bool(d.get("ativo", True)),
            setor=normalize_sector(d.get("setor")),
            cargo=(str(d["cargo"]).strip() or None) if d.get("cargo") is not None else None,
        )


class SpringClient:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def listar_trabalhadores(self) -> list[Trabalhador]:
        resp = self._client.get("/api/trabalhadores")
        resp.raise_for_status()
        return [Trabalhador.from_json(item) for item in resp.json()]

    def buscar_trabalhador(self, trabalhador_id: str) -> Optional[Trabalhador]:
        resp = self._client.get(f"/api/trabalhadores/{trabalhador_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return Trabalhador.from_json(resp.json())

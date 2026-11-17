"""Sincroniza o cadastro do Spring Boot com o serviço de identidade (Python).

Regras (decididas com a Sophia):
  * O Spring é a FONTE do cadastro administrativo; o Identity guarda uma
    cópia com o que a visão precisa (código, nome, setor, cargo, status).
  * Elo entre os dois: `matricula` (Spring) == `registration` (Identity).
    As duas são únicas, então não precisamos de tabela de mapeamento.
  * A sincronização é IDEMPOTENTE: rodar de novo não duplica nem estraga.
  * NÃO mexe em biometria. Cadastrar rosto exige consentimento explícito do
    titular e é um passo separado (/employees/{id}/biometric-enrollment).
    Ter cadastro NÃO significa ser reconhecido na câmera.
  * Setor/cargo vêm do Spring quando informados (`setor` = um dos códigos de
    app/sectors.py). Ausente => mantém o que já está (padrão só na criação).
    Código de setor desconhecido => reportado e ignorado: não adivinhamos.
  * Nunca apaga: trabalhador que sumiu do Spring é só reportado, e o
    `ativo=false` vira INACTIVE no Identity.
  * Falha ao falar com o Spring = nada é alterado e o erro é reportado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.sectors import is_valid_sector
from app.spring_client import SpringClient, Trabalhador


@dataclass
class SyncReport:
    created: list[str] = field(default_factory=list)      # matrículas
    updated: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    missing_in_spring: list[str] = field(default_factory=list)  # só no Identity
    errors: list[str] = field(default_factory=list)
    unknown_sector: list[str] = field(default_factory=list)  # "matrícula: código" (não adivinhamos)
    spring_reachable: bool = True

    def summary(self) -> dict:
        return {
            "spring_reachable": self.spring_reachable,
            "created": len(self.created),
            "updated": len(self.updated),
            "unchanged": len(self.unchanged),
            "missing_in_spring": len(self.missing_in_spring),
            "unknown_sector": len(self.unknown_sector),
            "errors": len(self.errors),
        }


def _wanted_status(t: Trabalhador) -> str:
    return "ACTIVE" if t.ativo else "INACTIVE"


def sync_workers(
    spring: SpringClient,
    identity,  # IdentityClient (ou falso com a mesma interface)
    default_sector: str = "PATIO_CARGA",
    default_role: str = "OPERADOR",
) -> SyncReport:
    report = SyncReport()
    try:
        trabalhadores = spring.listar_trabalhadores()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        report.spring_reachable = False
        report.errors.append(f"Spring indisponível ou resposta inesperada: {exc}")
        return report

    try:
        existing = {e["registration"]: e for e in identity.list_employees()}
    except httpx.HTTPError as exc:
        report.errors.append(f"Identity indisponível: {exc}")
        return report

    seen: set[str] = set()
    for t in trabalhadores:
        if t.matricula in seen:  # protege contra matrícula repetida na resposta
            report.errors.append(f"Matrícula repetida no Spring: {t.matricula}")
            continue
        seen.add(t.matricula)
        try:
            current = existing.get(t.matricula)
            # Setor: só vale se for um dos códigos conhecidos. Código desconhecido é
            # reportado e IGNORADO (nunca adivinhamos nem sobrescrevemos o que já existe).
            sector_ok = t.setor if is_valid_sector(t.setor) else None
            if t.setor and sector_ok is None:
                report.unknown_sector.append(f"{t.matricula}: {t.setor}")
            if current is None:
                created = identity.create_employee(
                    registration=t.matricula, name=t.nome,
                    sector=sector_ok or default_sector, role_title=t.cargo or default_role,
                )
                if not t.ativo:
                    identity.update_employee(created["id"], status="INACTIVE")
                report.created.append(t.matricula)
                continue
            changes = {}
            if current["name"] != t.nome:
                changes["name"] = t.nome
            if current["status"] != _wanted_status(t):
                changes["status"] = _wanted_status(t)
            # Só muda setor/cargo se o Spring informou; ausência não apaga o que já está.
            if sector_ok and current.get("sector") != sector_ok:
                changes["sector"] = sector_ok
            if t.cargo and current.get("role_title") != t.cargo:
                changes["role_title"] = t.cargo
            if changes:
                identity.update_employee(current["id"], **changes)
                report.updated.append(t.matricula)
            else:
                report.unchanged.append(t.matricula)
        except httpx.HTTPError as exc:
            report.errors.append(f"{t.matricula}: {exc}")

    report.missing_in_spring = sorted(set(existing) - seen)
    return report

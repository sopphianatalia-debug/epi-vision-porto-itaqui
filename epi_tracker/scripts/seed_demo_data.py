#!/usr/bin/env python3
"""
Popula um cenario de demonstracao de terminal portuario -- via chamadas
REAIS a API do epi_tracker (POST /areas, /checkpoints, /trackers, /ppe,
/ppe/{id}/assign, /demo/location), nunca com dado fabricado direto no
frontend. Isso significa que tudo que aparecer na interface depois de
rodar este script eh dado que passou pelo backend de verdade -- e pode
ser substituido, a qualquer momento, por integracoes reais (leitores
BLE/RFID/UWB de verdade), sem tocar em uma linha do frontend.

Uso:
    python3 scripts/seed_demo_data.py [--url http://127.0.0.1:8010/api/v1]

So biblioteca padrao (urllib) -- roda em qualquer ambiente, sem precisar
instalar httpx/requests so para popular dados de demonstracao.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def call(base_url: str, method: str, path: str, body: dict | None = None) -> dict:
    url = base_url + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"  aviso: {method} {path} -> {exc.code}: {detail}", file=sys.stderr)
        return {}


# Areas reais de um terminal portuario -- seção 2 do pedido de melhoria.
# `type` usa os codigos reconhecidos por frontend/src/utils/portZones.js;
# qualquer outro tipo também funcionaria (cairia numa zona genérica), isso
# só deixa a planta mais organizada visualmente.
AREAS = [
    {"area_id": "CAIS-01", "name": "Cais 01 - Berço de Atracação", "type": "CAIS"},
    {"area_id": "NAVIOS-01", "name": "Área de Operação de Navios", "type": "NAVIOS"},
    {"area_id": "PATIO-ARM-01", "name": "Pátio de Armazenagem", "type": "PATIO_ARMAZENAGEM"},
    {"area_id": "PATIO-CAM-01", "name": "Pátio de Caminhões", "type": "PATIO_CAMINHOES"},
    {"area_id": "CARGA-DESCARGA-01", "name": "Área de Carga e Descarga", "type": "CARGA_DESCARGA"},
    {"area_id": "ARMAZEM-01", "name": "Armazém Operacional 01", "type": "ARMAZEM"},
    {"area_id": "OFICINA-01", "name": "Oficina de Manutenção", "type": "OFICINA"},
    {"area_id": "PORTARIA-01", "name": "Portaria Principal", "type": "PORTARIA"},
    {"area_id": "ADM-01", "name": "Área Administrativa", "type": "ADMINISTRATIVA"},
    {"area_id": "RESTRITA-01", "name": "Área de Acesso Restrito", "type": "RESTRITA"},
]

CHECKPOINTS = [
    {"checkpoint_id": "CK-PORTARIA", "area_id": "PORTARIA-01", "name": "Entrada Principal", "camera_id": "CAM-PORTARIA"},
    {"checkpoint_id": "CK-CAIS", "area_id": "CAIS-01", "name": "Acesso ao Cais", "camera_id": "CAM-CAIS-01"},
    {"checkpoint_id": "CK-PATIO", "area_id": "PATIO-ARM-01", "name": "Entrada do Pátio", "camera_id": "CAM-PATIO-01"},
    {"checkpoint_id": "CK-ARMAZEM", "area_id": "ARMAZEM-01", "name": "Acesso ao Armazém", "camera_id": "CAM-ARMAZEM-01"},
    {"checkpoint_id": "CK-CARGA", "area_id": "CARGA-DESCARGA-01", "name": "Área de Carga/Descarga", "camera_id": "CAM-CARGA-01"},
]

# tracker_id, tipo de EPI, funcionário atribuído, área onde o tracker está
TRACKERS = [
    ("TRACKER-001", "helmet", "FUNC-000001", "CAIS-01"),
    ("TRACKER-002", "vest", "FUNC-000001", "CAIS-01"),
    ("TRACKER-003", "helmet", "FUNC-000002", "PATIO-ARM-01"),
    ("TRACKER-004", "boots", "FUNC-000002", "PATIO-ARM-01"),
    ("TRACKER-005", "helmet", "FUNC-000003", "ARMAZEM-01"),
    ("TRACKER-006", "gloves", "FUNC-000004", "CARGA-DESCARGA-01"),
    ("TRACKER-007", "helmet", "FUNC-000005", "OFICINA-01"),
    ("TRACKER-008", "vest", "FUNC-000006", "PATIO-CAM-01"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8010/api/v1")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    print(f"Populando dados de demonstração em {base} ...")

    print("Cadastrando áreas...")
    for area in AREAS:
        call(base, "POST", "/areas", area)

    print("Cadastrando checkpoints...")
    for cp in CHECKPOINTS:
        call(base, "POST", "/checkpoints", cp)

    print("Cadastrando trackers, EPIs e localizações...")
    for tracker_id, ppe_type, employee_id, area_id in TRACKERS:
        call(base, "POST", "/trackers", {"technology": "MOCK", "tracker_id": tracker_id})
        ppe = call(base, "POST", "/ppe", {"ppe_type": ppe_type, "tracker_id": tracker_id})
        if ppe.get("ppe_id"):
            call(base, "POST", f"/ppe/{ppe['ppe_id']}/assign", {"employee_id": employee_id})
        call(base, "POST", "/demo/location", {"tracker_id": tracker_id, "area_id": area_id})
        call(base, "POST", f"/trackers/{tracker_id}/poll", {})

    print("Registrando verificações de segurança de exemplo...")
    call(base, "POST", "/checks", {
        "employee_id": "FUNC-000001", "area_id": "CAIS-01", "checkpoint_id": "CK-CAIS",
        "status": "COMPLIANT", "detected_ppe": ["helmet", "vest"],
    })
    call(base, "POST", "/checks", {
        "employee_id": "FUNC-000004", "area_id": "CARGA-DESCARGA-01", "checkpoint_id": "CK-CARGA",
        "status": "NON_COMPLIANT", "detected_ppe": ["gloves"], "missing_ppe": ["helmet"],
    })

    print("\nConcluído. Abra o frontend para ver os dados.")


if __name__ == "__main__":
    main()

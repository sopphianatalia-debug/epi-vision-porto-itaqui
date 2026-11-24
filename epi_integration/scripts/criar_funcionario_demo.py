"""Cadastra (ou reaproveita) o funcionário de demonstração no Identity, com nome, cargo e setor.

Serve para testar o nome no aviso e na revisão sem depender do Spring. Idempotente: se a matrícula já existir,
só mostra o código. Cadastra a "biometria de demonstração" (mock, pelo código), nunca um rosto real.

Uso:  python scripts/criar_funcionario_demo.py [--name "Sophia (voluntária)"] [--role "Operadora"] [--sector PIER_BORDO]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# O mesmo segredo dos serviços (o subir_local.sh grava em .local/segredos.env).
_seg = Path(__file__).resolve().parents[2] / ".local" / "segredos.env"
if not os.environ.get("EPI_JWT_SECRET") and _seg.exists():
    for line in _seg.read_text().splitlines():
        if line.startswith("EPI_JWT_SECRET="):
            os.environ["EPI_JWT_SECRET"] = line.split("=", 1)[1].strip()

from app.identity_client import IdentityClient  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--identity-url", default="http://127.0.0.1:8001/api/v1")
    ap.add_argument("--registration", default="DEMO-0001")
    ap.add_argument("--name", default="Sophia (voluntária)")
    ap.add_argument("--role", default="Operadora")
    ap.add_argument("--sector", default="PIER_BORDO")
    a = ap.parse_args()
    if not os.environ.get("EPI_JWT_SECRET"):
        print("Falta EPI_JWT_SECRET (rode antes ./scripts/subir_local.sh start, que cria .local/segredos.env).")
        return 2
    ident = IdentityClient(a.identity_url)
    try:
        found = next((e for e in ident.list_employees() if e["registration"] == a.registration), None)
        if found:
            print(f"Já existe: {found['employee_code']} · {found['name']} · {found['role_title']} · {found['sector']}")
            emp = found
        else:
            emp = ident.create_employee(a.registration, a.name, a.sector, a.role)
            ident.enroll(employee_id=emp["id"], seed=emp["employee_code"])
            print(f"Criado: {emp['employee_code']} · {emp['name']} · {emp['role_title']} · {emp['sector']}")
        if emp["employee_code"] != "FUNC-000001":
            print(f"ATENÇÃO: o código é {emp['employee_code']}. Rode a câmera com EPI_PIPELINE_DEMO_EMPLOYEE_SEED={emp['employee_code']} "
                  f"./scripts/camera_local.sh")
        else:
            print("Pronto: rode ./scripts/camera_local.sh")
    finally:
        ident.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

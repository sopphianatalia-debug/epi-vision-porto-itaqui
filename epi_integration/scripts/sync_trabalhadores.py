"""Sincroniza o cadastro do Spring Boot (Diego) com o Identity.

Uso (com o Spring em :8080 e os serviços da demo no ar):
  python scripts/sync_trabalhadores.py --spring-url http://127.0.0.1:8080
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.identity_client import IdentityClient  # noqa: E402
from app.spring_client import SpringClient  # noqa: E402
from app.worker_sync import sync_workers  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spring-url", default="http://127.0.0.1:8080")
    ap.add_argument("--identity-url", default="http://127.0.0.1:8001/api/v1")
    ap.add_argument("--sector", default="PATIO_CARGA")
    ap.add_argument("--role", default="OPERADOR")
    a = ap.parse_args()
    spring, identity = SpringClient(a.spring_url), IdentityClient(a.identity_url)
    try:
        report = sync_workers(spring, identity, a.sector, a.role)
    finally:
        spring.close(); identity.close()
    print(json.dumps(report.summary(), ensure_ascii=False, indent=2))
    for label in ("created", "updated", "missing_in_spring", "unknown_sector", "errors"):
        for item in getattr(report, label):
            print(f"  {label}: {item}")
    return 0 if report.spring_reachable and not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

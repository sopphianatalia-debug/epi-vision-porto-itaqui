"""Cria o primeiro usuário (ou outros) sem expor a senha na linha de comando.

    EPI_JWT_SECRET=... AUTH_DB_PATH=./auth.db python -m app.cli create-user --username ana --name "Ana Lima" --role SUPERVISOR
"""
from __future__ import annotations

import argparse
import getpass
import sys

from app.api.deps import get_service
from app.service import AuthError


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="epi_auth")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user")
    c.add_argument("--username", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--role", required=True, choices=["OPERADOR", "SUPERVISOR"])
    args = p.parse_args(argv)
    pwd = getpass.getpass("Senha: ")
    if pwd != getpass.getpass("Repita a senha: "):
        print("As senhas não conferem.", file=sys.stderr)
        return 2
    try:
        u = get_service().create_user(args.username, args.name, args.role, pwd)
    except AuthError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    print(f"Usuário criado: {u.username} ({u.role})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Quem é o trabalhador: nome, cargo e setor vêm do cadastro (Spring -> Identity), nunca guardados no incidente.

O incidente guarda só o código (FUNC-xxxxxx). Esta consulta é feita na hora, só para o supervisor, e é
tolerante a falhas: se o cadastro estiver fora do ar, a tela continua mostrando o código.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt


class DirectoryDisabled(Exception):
    """INC_IDENTITY_URL não configurada."""


class DirectoryUnavailable(Exception):
    """Cadastro fora do ar ou recusou a chamada."""


class WorkerNotFound(Exception):
    pass


_FIELDS = ("employee_code", "name", "role_title", "sector", "status")


class WorkerDirectory:
    def __init__(self, identity_url: str, secret: Optional[str], timeout: float = 2.0, opener=None) -> None:
        self.base = (identity_url or "").rstrip("/")
        self.secret = secret or os.environ.get("EPI_JWT_SECRET")
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen

    def _token(self) -> str:
        now = datetime.now(timezone.utc)
        return jwt.encode({"sub": "epi-incident", "role": "SECURITY_MANAGER", "iat": now,
                           "exp": now + timedelta(minutes=5)}, self.secret, algorithm="HS256")

    def lookup(self, employee_code: str) -> dict:
        if not self.base:
            raise DirectoryDisabled("Cadastro de trabalhadores não configurado (INC_IDENTITY_URL).")
        if not self.secret:
            raise DirectoryUnavailable("Sem segredo para consultar o cadastro.")
        url = f"{self.base}/employees/by-code/{urllib.parse.quote(employee_code, safe='')}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._token()}"})
        try:
            with self._open(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise WorkerNotFound(employee_code) from exc
            raise DirectoryUnavailable(f"Cadastro respondeu {exc.code}.") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise DirectoryUnavailable("Cadastro indisponível.") from exc
        # Só o necessário para o supervisor: nada de biometria, status biométrico ou datas.
        return {k: data.get(k) for k in _FIELDS}

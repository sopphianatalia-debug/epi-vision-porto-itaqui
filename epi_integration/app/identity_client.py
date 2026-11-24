"""Cliente HTTP do epi_identity — o único dos quatro serviços que exige
autenticação (JWT + RBAC). A integração minta seu próprio token, usando o
mesmo segredo (EPI_JWT_SECRET) passado ao subprocesso pelo runner — não há
usuário/senha real, é exatamente o mecanismo que os próprios testes do
epi_identity usam (`tests/conftest.py::auth_header`), só que fora do
processo do módulo.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.clients import ServiceClient

# Segredo de teste (público!). Fora de testes, defina EPI_JWT_SECRET no ambiente: o serviço e este cliente usam o mesmo.
JWT_SECRET = os.environ.get("EPI_JWT_SECRET") or "integration-tests-shared-secret-please-ignore"  # sem variável: deve casar com runner.py
JWT_ALGORITHM = "HS256"


def mint_token(subject: str = "epi-integration", role: str = "SECURITY_MANAGER") -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "role": role, "iat": now, "exp": now + timedelta(minutes=30)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class IdentityClient(ServiceClient):
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        super().__init__(base_url, timeout)
        token = mint_token()
        self._client.headers["Authorization"] = f"Bearer {token}"

    def create_employee(self, registration: str, name: str, sector: str = "PATIO_CARGA",
                         role_title: str = "OPERADOR") -> dict:
        resp = self._client.post(
            "/employees",
            json={"registration": registration, "name": name, "sector": sector, "role_title": role_title},
        )
        resp.raise_for_status()
        return resp.json()

    def list_employees(self, page_size: int = 100) -> list[dict]:
        """Lista TODOS os funcionários, paginando (a API pagina em 100)."""
        out: list[dict] = []
        offset = 0
        while True:
            resp = self._client.get("/employees", params={"limit": page_size, "offset": offset})
            resp.raise_for_status()
            page = resp.json()
            out.extend(page)
            if len(page) < page_size:
                return out
            offset += page_size

    def update_employee(self, employee_id: str, **fields) -> dict:
        resp = self._client.put(f"/employees/{employee_id}", json=fields)
        resp.raise_for_status()
        return resp.json()

    def enroll(self, employee_id: str, seed: str, quality: float = 0.95, consent: bool = True) -> dict:
        resp = self._client.post(
            f"/employees/{employee_id}/biometric-enrollment",
            json={"frame": _frame(seed, quality), "consent": consent},
        )
        resp.raise_for_status()
        return resp.json()

    def match(self, camera_id: str, seed: str, person_track_id: Optional[str] = None,
              quality: float = 0.95) -> dict:
        body = {"camera_id": camera_id, "frame": _frame(seed, quality)}
        if person_track_id is not None:
            body["person_track_id"] = person_track_id
        resp = self._client.post("/recognition/match", json=body)
        resp.raise_for_status()
        return resp.json()

    def metrics(self) -> dict:
        resp = self._client.get("/recognition/metrics")
        resp.raise_for_status()
        return resp.json()

    def list_employees(self) -> list[dict]:
        resp = self._client.get("/employees")
        resp.raise_for_status()
        return resp.json()


def _frame(seed: str, quality: float = 0.95) -> dict:
    """Formato do frame mock — ver epi_identity/app/recognition/providers/
    mock_provider.py. `seed` é o texto determinístico que vira o embedding."""
    return {"faces": [{"bbox": [0, 0, 100, 100], "seed": seed, "quality": quality,
                        "single_face": True, "face_visible": True}]}

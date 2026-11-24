"""Nome, cargo e setor do trabalhador do incidente. Só o supervisor consulta; o operador vê apenas o código."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_workers
from app.auth import current_user
from app.workers import DirectoryDisabled, DirectoryUnavailable, WorkerDirectory, WorkerNotFound

router = APIRouter(tags=["workers"])


@router.get("/workers/{employee_code}")
def worker(employee_code: str, user: Optional[dict] = Depends(current_user),
           directory: WorkerDirectory = Depends(get_workers)):
    if user is None:
        raise HTTPException(status_code=503, detail="Consulta de trabalhador exige login ativo (INC_AUTH_MODE=required).")
    if user["role"] != "SUPERVISOR":
        raise HTTPException(status_code=403, detail="Somente supervisor.")
    try:
        return directory.lookup(employee_code)
    except WorkerNotFound:
        raise HTTPException(status_code=404, detail="Trabalhador não encontrado no cadastro.")
    except DirectoryDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except DirectoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

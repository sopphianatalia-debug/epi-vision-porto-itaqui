from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_principal, require_permission
from app.database import get_session
from app.schemas.employee import EmployeeCreate, EmployeeOut, EmployeeUpdate
from app.security.auth import Principal
from app.security.rbac import Permission
from app.services import employee_service

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(
    data: EmployeeCreate,
    session: AsyncSession = Depends(get_session),
    actor: Principal = Depends(require_permission(Permission.EMPLOYEE_WRITE)),
):
    return await employee_service.create_employee(session, data, actor)


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_permission(Permission.EMPLOYEE_READ)),
):
    return await employee_service.list_employees(session, limit, offset)


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: str,
    session: AsyncSession = Depends(get_session),
    _: Principal = Depends(require_permission(Permission.EMPLOYEE_READ)),
):
    try:
        return await employee_service.get_employee(session, employee_id)
    except employee_service.EmployeeNotFound:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")


@router.put("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: str,
    data: EmployeeUpdate,
    session: AsyncSession = Depends(get_session),
    actor: Principal = Depends(require_permission(Permission.EMPLOYEE_WRITE)),
):
    try:
        return await employee_service.update_employee(session, employee_id, data, actor)
    except employee_service.EmployeeNotFound:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: str,
    session: AsyncSession = Depends(get_session),
    actor: Principal = Depends(require_permission(Permission.EMPLOYEE_DELETE)),
):
    try:
        await employee_service.delete_employee(session, employee_id, actor)
    except employee_service.EmployeeNotFound:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado.")

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import utcnow
from app.enums import AuditAction, EmployeeStatus
from app.models import Employee
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.security.auth import Principal
from app.services.audit_service import record_audit


class EmployeeNotFound(Exception):
    pass


async def _next_employee_code(session: AsyncSession) -> str:
    # Referência simples. Em produção usar sequence/identity do banco.
    total = await session.scalar(select(func.count()).select_from(Employee))
    return f"FUNC-{(total or 0) + 1:06d}"


async def create_employee(
    session: AsyncSession, data: EmployeeCreate, actor: Principal
) -> Employee:
    employee = Employee(
        employee_code=await _next_employee_code(session),
        registration=data.registration,
        name=data.name,
        sector=data.sector,
        role_title=data.role_title,
    )
    session.add(employee)
    await session.flush()
    await record_audit(
        session,
        AuditAction.EMPLOYEE_CREATE,
        actor=actor.subject,
        actor_role=actor.role.value,
        resource_type="employee",
        resource_id=employee.employee_code,
    )
    await session.commit()
    await session.refresh(employee)
    return employee


async def get_employee(session: AsyncSession, employee_id: str) -> Employee:
    employee = await session.get(Employee, employee_id)
    if employee is None or employee.is_deleted:
        raise EmployeeNotFound(employee_id)
    return employee


async def get_by_code(session: AsyncSession, employee_code: str) -> Optional[Employee]:
    return await session.scalar(
        select(Employee).where(
            Employee.employee_code == employee_code, Employee.is_deleted.is_(False)
        )
    )


async def list_employees(session: AsyncSession, limit: int = 100, offset: int = 0) -> list[Employee]:
    rows = await session.scalars(
        select(Employee)
        .where(Employee.is_deleted.is_(False))
        .order_by(Employee.employee_code)
        .limit(limit)
        .offset(offset)
    )
    return list(rows)


async def update_employee(
    session: AsyncSession, employee_id: str, data: EmployeeUpdate, actor: Principal
) -> Employee:
    employee = await get_employee(session, employee_id)
    for field_name, value in data.model_dump(exclude_unset=True).items():
        if field_name == "status" and value is not None:
            employee.status = EmployeeStatus(value).value
        elif value is not None:
            setattr(employee, field_name, value)
    await record_audit(
        session,
        AuditAction.EMPLOYEE_UPDATE,
        actor=actor.subject,
        actor_role=actor.role.value,
        resource_type="employee",
        resource_id=employee.employee_code,
        details=data.model_dump(exclude_unset=True),
    )
    await session.commit()
    await session.refresh(employee)
    return employee


async def delete_employee(session: AsyncSession, employee_id: str, actor: Principal) -> None:
    employee = await get_employee(session, employee_id)
    employee.is_deleted = True
    employee.deleted_at = utcnow()
    employee.status = EmployeeStatus.INACTIVE.value
    await record_audit(
        session,
        AuditAction.EMPLOYEE_DELETE,
        actor=actor.subject,
        actor_role=actor.role.value,
        resource_type="employee",
        resource_id=employee.employee_code,
    )
    await session.commit()

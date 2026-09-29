import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.hr import service
from app.hr.models import EmploymentStatus
from app.hr.schemas import (
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    LeaveRequestCreate,
    LeaveRequestOut,
)
from app.users.models import User

router = APIRouter(prefix="/hr", tags=["hr"])


@router.get("/employees", response_model=list[EmployeeOut])
async def list_employees(
    department: str | None = Query(default=None),
    employment_status: EmploymentStatus | None = Query(default=None),
    q: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.read")),
) -> list[EmployeeOut]:
    return await service.list_employees(session, department=department, employment_status=employment_status, q=q)


@router.post("/employees", response_model=EmployeeOut, status_code=201)
async def create_employee(
    body: EmployeeCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.write")),
) -> EmployeeOut:
    return await service.create_employee(session, body)


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.read")),
) -> EmployeeOut:
    return await service.get_employee(session, employee_id)


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: uuid.UUID,
    body: EmployeeUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.write")),
) -> EmployeeOut:
    return await service.update_employee(session, employee_id, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/employees/{employee_id}/activate", response_model=EmployeeOut)
async def activate_employee(
    employee_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.write")),
) -> EmployeeOut:
    return await service.set_employee_active(session, employee_id, True, actor_id=current.id, actor_role=current.role.code)


@router.post("/employees/{employee_id}/deactivate", response_model=EmployeeOut)
async def deactivate_employee(
    employee_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.write")),
) -> EmployeeOut:
    return await service.set_employee_active(session, employee_id, False, actor_id=current.id, actor_role=current.role.code)


@router.get("/leave-requests", response_model=list[LeaveRequestOut])
async def list_leave_requests(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.read")),
) -> list[LeaveRequestOut]:
    return await service.list_leave_requests(session)


@router.post("/leave-requests", response_model=LeaveRequestOut, status_code=201)
async def submit_leave(
    body: LeaveRequestCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.read")),
) -> LeaveRequestOut:
    return await service.submit_leave_request(session, body)


@router.post("/leave-requests/{leave_id}/decide", response_model=LeaveRequestOut)
async def decide_leave(
    leave_id: str,
    approve: bool,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.approve_leave")),
) -> LeaveRequestOut:
    return await service.decide_leave_request(session, leave_id, approve, actor_id=current.id, actor_role=current.role.code)

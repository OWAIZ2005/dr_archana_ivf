import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.core.exceptions import ConflictError, NotFoundError
from app.events.bus import EventType, emit
from app.hr.models import Employee, EmploymentStatus, LeaveRequest, LeaveStatus
from app.hr.schemas import EmployeeCreate, EmployeeUpdate, LeaveRequestCreate


async def create_employee(session: AsyncSession, data: EmployeeCreate) -> Employee:
    employee = Employee(**data.model_dump())
    session.add(employee)
    await session.flush()
    return employee


async def list_employees(
    session: AsyncSession, *, department: str | None = None, employment_status: EmploymentStatus | None = None, q: str | None = None,
) -> list[Employee]:
    stmt = select(Employee)
    if department:
        stmt = stmt.where(Employee.department == department)
    if employment_status:
        stmt = stmt.where(Employee.employment_status == employment_status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Employee.full_name.ilike(like), Employee.designation.ilike(like), Employee.biometric_id.ilike(like)))
    stmt = stmt.order_by(Employee.full_name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_employee(session: AsyncSession, employee_id: uuid.UUID) -> Employee:
    employee = await session.get(Employee, employee_id)
    if not employee:
        raise NotFoundError("Employee not found")
    return employee


async def update_employee(session: AsyncSession, employee_id: uuid.UUID, data: EmployeeUpdate, *, actor_id: uuid.UUID, actor_role: str) -> Employee:
    employee = await get_employee(session, employee_id)
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(employee, k, v)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role, action="hr.employee_updated",
        entity_type="Employee", entity_id=str(employee.id),
        after_state={k: (v.value if hasattr(v, "value") else v) for k, v in changes.items()},
    )
    return employee


async def set_employee_active(session: AsyncSession, employee_id: uuid.UUID, active: bool, *, actor_id: uuid.UUID, actor_role: str) -> Employee:
    employee = await get_employee(session, employee_id)
    employee.employment_status = EmploymentStatus.ACTIVE if active else EmploymentStatus.INACTIVE
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="hr.employee_activated" if active else "hr.employee_deactivated",
        entity_type="Employee", entity_id=str(employee.id), after_state={"employment_status": employee.employment_status.value},
    )
    return employee


async def list_leave_requests(session: AsyncSession) -> list[LeaveRequest]:
    result = await session.execute(select(LeaveRequest).order_by(LeaveRequest.created_at.desc()))
    return list(result.scalars().all())


async def submit_leave_request(session: AsyncSession, data: LeaveRequestCreate) -> LeaveRequest:
    days_requested = (data.to_date - data.from_date).days + 1
    employee = await session.get(Employee, data.employee_id)
    if not employee:
        raise NotFoundError("Employee not found")
    if days_requested > employee.leave_balance_days:
        raise ConflictError(
            f"Requested {days_requested} days but only {employee.leave_balance_days} remain.",
            error_code="insufficient_leave_balance",
        )

    leave = LeaveRequest(**data.model_dump())
    session.add(leave)
    await session.flush()

    await emit(
        session, event_type=EventType.LEAVE_REQUEST_SUBMITTED, entity_type="LeaveRequest", entity_id=str(leave.id),
        payload={"employee_id": str(data.employee_id), "days": days_requested},
    )
    return leave


async def decide_leave_request(
    session: AsyncSession, leave_id: uuid.UUID, approve: bool, *, actor_id: uuid.UUID, actor_role: str
) -> LeaveRequest:
    leave = await session.get(LeaveRequest, leave_id)
    if not leave:
        raise NotFoundError("Leave request not found")
    if leave.status != LeaveStatus.PENDING:
        raise ConflictError("This leave request has already been decided.")

    leave.status = LeaveStatus.APPROVED if approve else LeaveStatus.REJECTED
    leave.approved_by_id = actor_id

    if approve:
        employee = await session.get(Employee, leave.employee_id)
        days = (leave.to_date - leave.from_date).days + 1
        employee.leave_balance_days -= days

    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="hr.leave_decided", entity_type="LeaveRequest", entity_id=str(leave.id),
        after_state={"status": leave.status.value},
    )
    return leave

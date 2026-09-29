"""Payroll, computed from attendance — spec §8/§9. One row per
(employee, month, year); `calculate`/`recalculate` re-derive it from
AttendanceRecord + HrSettings and always show a transparent breakdown
rather than only the final number. Never auto-transitions to PAID —
that is always a separate, explicit HR action (spec §9's "Do not
automatically mark payroll as paid")."""
from __future__ import annotations

import calendar
import enum
import uuid
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.audit.service import record_audit_event
from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base, get_db
from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.hr.attendance import compute_employee_month_ledger, get_period
from app.hr.models import AttendancePeriodStatus, AttendanceRecord, AttendanceStatus, Employee
from app.hr.settings import get_settings
from app.users.models import User


class PayrollStatus(str, enum.Enum):
    # DRAFT = calculated but the month's attendance period isn't finalized
    # yet (or was finalized with unprocessed days via override) — cannot
    # be approved. CALCULATED = attendance period is finalized clean, ready
    # for HR review/approval. Spec §10/§29's month-end workflow: Calculate
    # Payroll -> Payroll Draft -> HR Review -> Approve -> Paid.
    DRAFT = "draft"
    CALCULATED = "calculated"
    APPROVED = "approved"
    PAID = "paid"


class Payroll(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payroll_records"
    __table_args__ = (UniqueConstraint("employee_id", "month", "year", name="uq_payroll_employee_month_year"),)

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    base_salary_rupees: Mapped[int] = mapped_column(Integer, nullable=False)
    working_days: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unprocessed_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    present_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    half_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    absent_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payable_days: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)

    per_day_rupees: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    deduction_rupees: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overtime_hours: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    overtime_amount_rupees: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    other_deductions_rupees: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_salary_rupees: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_attendance_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    status: Mapped[PayrollStatus] = mapped_column(Enum(PayrollStatus), default=PayrollStatus.CALCULATED, index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculated_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


def _round_rupees(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


async def calculate_payroll(
    session: AsyncSession, *, employee_id: uuid.UUID, month: int, year: int, actor_id: uuid.UUID,
    other_deductions_rupees: int = 0,
) -> Payroll:
    """Always uses app.hr.attendance.compute_employee_month_ledger — the
    same function the Monthly Attendance screen reads — so payroll can
    never disagree with what HR sees there about present/half/absent/
    unprocessed counts (spec §7: "Payroll must use the monthly attendance
    ledger, not simply whatever attendance records happen to exist").
    Calculation always succeeds (so HR can preview numbers mid-month),
    but lands in DRAFT — not approvable — unless the month's
    AttendancePeriod has been finalized; see approve_payroll."""
    employee = await session.get(Employee, employee_id)
    if not employee:
        raise NotFoundError("Employee not found")
    if employee.monthly_salary_rupees is None:
        raise ValidationFailedError("This employee has no monthly salary on file — set it in Employee Management first.")

    settings = await get_settings(session)
    ledger = await compute_employee_month_ledger(session, employee_id, month, year)
    period = await get_period(session, month, year)
    is_complete = ledger.unprocessed_days == 0

    half_fraction = Decimal(str(settings.half_day_pay_fraction))
    absent_fraction = Decimal(str(settings.absent_day_pay_fraction))
    payable_days = (
        Decimal(ledger.present_days)
        + Decimal(ledger.half_days) * half_fraction
        + Decimal(ledger.absent_days) * absent_fraction
    )

    # working_days for the pay-rate denominator is the ledger's own count
    # of actual working days this month (Sundays excluded) — not the flat
    # HrSettings.working_days_per_month, which was only ever an approximation.
    working_days = ledger.working_days or settings.working_days_per_month
    base = Decimal(employee.monthly_salary_rupees)
    per_day = base / Decimal(working_days) if working_days else Decimal(0)
    earned = per_day * payable_days
    attendance_deduction = _round_rupees(base - earned)

    full_day_minutes = int(Decimal(str(settings.full_day_hours)) * 60)
    # Overtime needs actual working_minutes, which the ledger's day entries
    # don't carry (they only carry status) — re-derive from the same date
    # range directly for the present-status days.
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    records = (await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.attendance_date >= start,
            AttendanceRecord.attendance_date <= end,
        )
    )).scalars().all()
    overtime_minutes = sum(
        max(0, (r.working_minutes or 0) - full_day_minutes)
        for r in records if r.status == AttendanceStatus.PRESENT
    )
    overtime_hours = Decimal(overtime_minutes) / Decimal(60)
    overtime_amount = _round_rupees(overtime_hours * Decimal(settings.overtime_rate_per_hour_rupees))

    other_deductions = max(0, other_deductions_rupees)
    net = int(base) - attendance_deduction - other_deductions + overtime_amount

    existing_payroll = (await session.execute(
        select(Payroll).where(Payroll.employee_id == employee_id, Payroll.month == month, Payroll.year == year)
    )).scalar_one_or_none()
    if existing_payroll and existing_payroll.status == PayrollStatus.PAID:
        raise ConflictError("This payroll has already been paid and cannot be recalculated.")
    if existing_payroll and existing_payroll.status == PayrollStatus.APPROVED:
        raise ConflictError("This payroll is already approved — reopen it isn't supported; recalculating an approved payroll is blocked to avoid silently changing an approved figure.")

    now = datetime.now(timezone.utc)
    if existing_payroll:
        payroll = existing_payroll
        payroll.approved_at = None
        payroll.approved_by_id = None
    else:
        payroll = Payroll(employee_id=employee_id, month=month, year=year)
        session.add(payroll)

    payroll.status = (
        PayrollStatus.CALCULATED if (is_complete or period.status == AttendancePeriodStatus.FINALIZED)
        else PayrollStatus.DRAFT
    )
    payroll.base_salary_rupees = employee.monthly_salary_rupees
    payroll.working_days = working_days
    payroll.processed_days = ledger.processed_days
    payroll.unprocessed_days = ledger.unprocessed_days
    payroll.present_days = ledger.present_days
    payroll.half_days = ledger.half_days
    payroll.absent_days = ledger.absent_days
    payroll.payable_days = payable_days
    payroll.per_day_rupees = per_day
    payroll.deduction_rupees = attendance_deduction
    payroll.overtime_hours = overtime_hours
    payroll.overtime_amount_rupees = overtime_amount
    payroll.other_deductions_rupees = other_deductions
    payroll.net_salary_rupees = net
    payroll.is_attendance_complete = is_complete
    payroll.calculated_at = now
    payroll.calculated_by_id = actor_id

    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role="system", action="hr.payroll_calculated",
        entity_type="Payroll", entity_id=str(payroll.id),
        after_state={"net_salary_rupees": net, "month": month, "year": year, "status": payroll.status.value, "unprocessed_days": ledger.unprocessed_days},
    )
    return payroll


async def list_payroll(session: AsyncSession, *, month: int | None, year: int | None, department: str | None, employee_id: uuid.UUID | None) -> list[Payroll]:
    stmt = select(Payroll, Employee).join(Employee, Employee.id == Payroll.employee_id)
    if month:
        stmt = stmt.where(Payroll.month == month)
    if year:
        stmt = stmt.where(Payroll.year == year)
    if department:
        stmt = stmt.where(Employee.department == department)
    if employee_id:
        stmt = stmt.where(Payroll.employee_id == employee_id)
    stmt = stmt.order_by(Payroll.year.desc(), Payroll.month.desc())
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def get_payroll(session: AsyncSession, payroll_id: uuid.UUID) -> Payroll:
    p = await session.get(Payroll, payroll_id)
    if not p:
        raise NotFoundError("Payroll record not found")
    return p


async def approve_payroll(session: AsyncSession, payroll_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str) -> Payroll:
    payroll = await get_payroll(session, payroll_id)
    if payroll.status == PayrollStatus.DRAFT:
        raise ConflictError(
            f"Attendance for {payroll.month}/{payroll.year} is not finalized "
            f"({payroll.unprocessed_days} working day(s) unprocessed) — finalize the attendance period "
            "before approving payroll, or finalize with an override if the gap is expected.",
            error_code="attendance_incomplete",
        )
    if payroll.status != PayrollStatus.CALCULATED:
        raise ConflictError(f"Cannot approve a payroll in '{payroll.status.value}' status.")
    payroll.status = PayrollStatus.APPROVED
    payroll.approved_at = datetime.now(timezone.utc)
    payroll.approved_by_id = actor_id
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role, action="hr.payroll_approved",
        entity_type="Payroll", entity_id=str(payroll.id), after_state={"status": "approved"},
    )
    return payroll


async def mark_payroll_paid(session: AsyncSession, payroll_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str) -> Payroll:
    payroll = await get_payroll(session, payroll_id)
    if payroll.status != PayrollStatus.APPROVED:
        raise ConflictError("Only an approved payroll can be marked as paid.")
    payroll.status = PayrollStatus.PAID
    payroll.paid_at = datetime.now(timezone.utc)
    payroll.paid_by_id = actor_id
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role, action="hr.payroll_paid",
        entity_type="Payroll", entity_id=str(payroll.id), after_state={"status": "paid"},
    )
    return payroll


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class PayrollCalculateRequest(BaseModel):
    employee_id: uuid.UUID
    month: int
    year: int
    other_deductions_rupees: int = 0


class PayrollOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: uuid.UUID
    month: int
    year: int
    base_salary_rupees: int
    working_days: int
    processed_days: int
    unprocessed_days: int
    present_days: int
    half_days: int
    absent_days: int
    payable_days: float
    per_day_rupees: float
    deduction_rupees: int
    overtime_hours: float
    overtime_amount_rupees: int
    other_deductions_rupees: int
    net_salary_rupees: int
    is_attendance_complete: bool
    status: PayrollStatus
    calculated_at: datetime
    approved_at: datetime | None
    paid_at: datetime | None


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #

router = APIRouter(prefix="/hr/payroll", tags=["hr-payroll"])


@router.post("/calculate", response_model=PayrollOut)
async def calculate_payroll_endpoint(
    body: PayrollCalculateRequest,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.payroll_process")),
) -> PayrollOut:
    return await calculate_payroll(
        session, employee_id=body.employee_id, month=body.month, year=body.year, actor_id=current.id,
        other_deductions_rupees=body.other_deductions_rupees,
    )


@router.get("", response_model=list[PayrollOut])
async def list_payroll_endpoint(
    month: int | None = Query(default=None),
    year: int | None = Query(default=None),
    department: str | None = Query(default=None),
    employee_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.payroll_read")),
) -> list[PayrollOut]:
    return await list_payroll(session, month=month, year=year, department=department, employee_id=employee_id)


@router.post("/{payroll_id}/approve", response_model=PayrollOut)
async def approve_payroll_endpoint(
    payroll_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.payroll_approve")),
) -> PayrollOut:
    return await approve_payroll(session, payroll_id, actor_id=current.id, actor_role=current.role.code)


@router.post("/{payroll_id}/mark-paid", response_model=PayrollOut)
async def mark_payroll_paid_endpoint(
    payroll_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.payroll_approve")),
) -> PayrollOut:
    return await mark_payroll_paid(session, payroll_id, actor_id=current.id, actor_role=current.role.code)

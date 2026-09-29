"""HR Dashboard Home — spec §2's single-screen operational overview.
Every figure here is a live aggregate over real rows (Employee,
AttendanceRecord, Payroll, Appointment/AppointmentStatusEvent), not a
separate cached/materialized summary table, so it can never drift from
what the Employees/Attendance/Payroll/Patient Flow screens themselves
show."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.appointments.models import Appointment, AppointmentStatusEvent
from app.core.database import get_db
from app.core.deps import require_permission
from app.hr.models import AttendanceRecord, AttendanceStatus, Employee, EmploymentStatus
from app.hr.payroll import Payroll, PayrollStatus
from app.hr.process import ACTIVE_STAGES, get_delays
from app.users.models import User

router = APIRouter(prefix="/hr/dashboard", tags=["hr-dashboard"])


class EmployeeStatsOut(BaseModel):
    total_employees: int
    present_today: int
    half_day_today: int
    absent_today: int
    late_arrivals: int
    currently_inside: int


class AttendanceStatsOut(BaseModel):
    attendance_percent: float
    avg_working_hours: float
    total_overtime_hours: float


class PayrollStatsOut(BaseModel):
    current_month_calculated: int
    pending_approval: int
    total_salary_this_month_rupees: int
    employees_with_deductions: int


class PatientOpsStatsOut(BaseModel):
    patients_in_process: int
    avg_waiting_time_minutes: float
    avg_consultation_time_minutes: float
    avg_pharmacy_time_minutes: float
    active_delays: int
    critical_delays: int


class HrDashboardOut(BaseModel):
    employees: EmployeeStatsOut
    attendance: AttendanceStatsOut
    payroll: PayrollStatsOut
    patient_ops: PatientOpsStatsOut


async def _avg_stage_dwell_minutes(session: AsyncSession, stage_value: str, today: date) -> float:
    """Average minutes between an event entering `stage_value` and the
    next event on that same appointment, for transitions into the stage
    that happened today and have since moved on — i.e. completed dwell
    times, not appointments still sitting in the stage."""
    events = (await session.execute(
        select(AppointmentStatusEvent)
        .where(AppointmentStatusEvent.to_status == stage_value, cast(AppointmentStatusEvent.changed_at, Date) == today)
        .order_by(AppointmentStatusEvent.appointment_id, AppointmentStatusEvent.changed_at)
    )).scalars().all()
    if not events:
        return 0.0

    by_appt: dict = {}
    for e in events:
        by_appt.setdefault(e.appointment_id, []).append(e)

    all_next = (await session.execute(
        select(AppointmentStatusEvent).where(AppointmentStatusEvent.appointment_id.in_(list(by_appt.keys())))
        .order_by(AppointmentStatusEvent.appointment_id, AppointmentStatusEvent.changed_at)
    )).scalars().all()
    by_appt_all: dict = {}
    for e in all_next:
        by_appt_all.setdefault(e.appointment_id, []).append(e)

    durations = []
    for appt_id, appt_events in by_appt_all.items():
        for i, e in enumerate(appt_events):
            if e.to_status != stage_value:
                continue
            if i + 1 < len(appt_events):
                nxt = appt_events[i + 1]
                durations.append((nxt.changed_at - e.changed_at).total_seconds() / 60)

    return round(sum(durations) / len(durations), 1) if durations else 0.0


@router.get("/summary", response_model=HrDashboardOut)
async def get_dashboard_summary(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.read")),
) -> HrDashboardOut:
    today = datetime.now(timezone.utc).date()

    total_employees = (await session.execute(
        select(func.count()).select_from(Employee).where(Employee.employment_status == EmploymentStatus.ACTIVE)
    )).scalar_one()

    today_records = (await session.execute(
        select(AttendanceRecord).where(AttendanceRecord.attendance_date == today)
    )).scalars().all()

    present = sum(1 for r in today_records if r.status == AttendanceStatus.PRESENT)
    half = sum(1 for r in today_records if r.status == AttendanceStatus.HALF_DAY)
    absent = sum(1 for r in today_records if r.status == AttendanceStatus.ABSENT)
    currently_inside = sum(1 for r in today_records if r.entry_time and not r.exit_time)

    from app.hr.settings import get_settings
    settings_row = await get_settings(session)
    grace = settings_row.late_arrival_grace_minutes
    std_start_h, std_start_m = (int(x) for x in settings_row.standard_start_time.split(":"))
    late_arrivals = 0
    for r in today_records:
        if not r.entry_time:
            continue
        threshold = r.entry_time.replace(hour=std_start_h, minute=std_start_m, second=0, microsecond=0)
        if (r.entry_time - threshold).total_seconds() / 60 > grace:
            late_arrivals += 1

    attendance_pct = round(100 * (present + half) / total_employees, 1) if total_employees else 0.0
    worked_minutes = [r.working_minutes for r in today_records if r.working_minutes]
    avg_hours = round((sum(worked_minutes) / len(worked_minutes)) / 60, 1) if worked_minutes else 0.0

    full_day_minutes = int(float(settings_row.full_day_hours) * 60)
    overtime_minutes_today = sum(max(0, m - full_day_minutes) for m in worked_minutes)
    total_overtime_hours = round(overtime_minutes_today / 60, 1)

    month, year = today.month, today.year
    month_payroll = (await session.execute(
        select(Payroll).where(Payroll.month == month, Payroll.year == year)
    )).scalars().all()
    current_calculated = sum(1 for p in month_payroll if p.status in (PayrollStatus.DRAFT, PayrollStatus.CALCULATED))
    pending_approval = sum(1 for p in month_payroll if p.status == PayrollStatus.CALCULATED)  # DRAFT can't be approved yet — see payroll.approve_payroll
    total_salary = sum(p.net_salary_rupees for p in month_payroll)
    with_deductions = sum(1 for p in month_payroll if p.deduction_rupees > 0)

    active_appt_count = (await session.execute(
        select(func.count()).select_from(Appointment).where(
            Appointment.status.in_(ACTIVE_STAGES), cast(Appointment.scheduled_at, Date) == today,
        )
    )).scalar_one()

    delays = await get_delays(session, today=today, only_delayed=True)
    critical = sum(1 for d in delays if d.severity == "critical")

    avg_waiting = await _avg_stage_dwell_minutes(session, "waiting", today)
    avg_consultation = await _avg_stage_dwell_minutes(session, "consultation", today)
    avg_pharmacy = await _avg_stage_dwell_minutes(session, "pharmacy", today)

    return HrDashboardOut(
        employees=EmployeeStatsOut(
            total_employees=total_employees, present_today=present, half_day_today=half,
            absent_today=absent, late_arrivals=late_arrivals, currently_inside=currently_inside,
        ),
        attendance=AttendanceStatsOut(
            attendance_percent=attendance_pct, avg_working_hours=avg_hours, total_overtime_hours=total_overtime_hours,
        ),
        payroll=PayrollStatsOut(
            current_month_calculated=current_calculated, pending_approval=pending_approval,
            total_salary_this_month_rupees=total_salary, employees_with_deductions=with_deductions,
        ),
        patient_ops=PatientOpsStatsOut(
            patients_in_process=active_appt_count, avg_waiting_time_minutes=avg_waiting,
            avg_consultation_time_minutes=avg_consultation, avg_pharmacy_time_minutes=avg_pharmacy,
            active_delays=len(delays), critical_delays=critical,
        ),
    )

"""HR Reports/export — spec §19. CSV export, generated synchronously and
streamed back directly. Deliberately not wired into app/reports' async
Celery job system (ReportType/job_generators) — these exports are small,
tabular, and fast to build in-request; the job queue exists for the
heavier PDF discharge-summary-style documents elsewhere in the app. If
HR reports later need to run over months of data, moving these into a
new ReportType there is the natural next step."""
from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.hr.attendance import list_attendance
from app.hr.models import AttendanceStatus, Employee
from app.hr.payroll import list_payroll
from app.hr.process import get_delays
from app.users.models import User

router = APIRouter(prefix="/hr/reports", tags=["hr-reports"])


def _csv_response(rows: list[list], header: list[str], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/attendance.csv")
async def export_attendance_csv(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    department: str | None = Query(default=None),
    status: AttendanceStatus | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.reports_export")),
) -> StreamingResponse:
    records = await list_attendance(session, from_date=from_date, to_date=to_date, department=department, employee_id=None, status=status)
    employees = {e.id: e for e in (await session.execute(select(Employee))).scalars().all()}
    rows = [
        [
            employees[r.employee_id].full_name if r.employee_id in employees else str(r.employee_id),
            employees[r.employee_id].department if r.employee_id in employees else "",
            r.attendance_date.isoformat(),
            r.entry_time.strftime("%H:%M") if r.entry_time else "",
            r.exit_time.strftime("%H:%M") if r.exit_time else "",
            f"{(r.working_minutes or 0) // 60}h {(r.working_minutes or 0) % 60}m" if r.working_minutes else "",
            r.status.value,
        ]
        for r in records
    ]
    return _csv_response(rows, ["Employee", "Department", "Date", "Entry", "Exit", "Working Hours", "Status"], "attendance_report.csv")


@router.get("/payroll.csv")
async def export_payroll_csv(
    month: int | None = Query(default=None),
    year: int | None = Query(default=None),
    department: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.reports_export")),
) -> StreamingResponse:
    records = await list_payroll(session, month=month, year=year, department=department, employee_id=None)
    employees = {e.id: e for e in (await session.execute(select(Employee))).scalars().all()}
    rows = [
        [
            employees[p.employee_id].full_name if p.employee_id in employees else str(p.employee_id),
            f"{p.month}/{p.year}", p.base_salary_rupees, p.present_days, p.half_days, p.absent_days,
            p.deduction_rupees, p.overtime_amount_rupees, p.net_salary_rupees, p.status.value,
        ]
        for p in records
    ]
    return _csv_response(
        rows,
        ["Employee", "Month", "Base Salary", "Present", "Half Day", "Absent", "Deduction", "Overtime", "Net Salary", "Status"],
        "payroll_report.csv",
    )


@router.get("/delays.csv")
async def export_delays_csv(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.reports_export")),
) -> StreamingResponse:
    from datetime import datetime, timezone
    delays = await get_delays(session, today=datetime.now(timezone.utc).date(), only_delayed=True)
    rows = [
        [str(d.patient_id), d.stage, d.threshold_minutes, d.actual_minutes, d.delay_minutes, d.delay_reason or "", d.started_at.date().isoformat()]
        for d in delays
    ]
    return _csv_response(rows, ["Patient ID", "Stage", "Expected (min)", "Actual (min)", "Delay (min)", "Reason", "Date"], "delay_report.csv")

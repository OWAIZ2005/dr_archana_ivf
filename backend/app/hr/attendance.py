"""Biometric attendance: Excel import (parse -> preview -> confirm, per
spec §4/§21's safety flow) and the attendance table/history HR reviews
against. `AttendanceRecord`/`AttendanceImport`/`AttendanceImportRow` live
in app/hr/models.py; this file is the parser + service + router, kept
separate the same way app/pharmacy/settings.py is its own file rather
than folded into pharmacy/router.py.

COLUMN MAPPING (spec §4: "do not assume exact column names, make it
configurable"): header matching is keyword-based and case-insensitive —
see COLUMN_ALIASES below. Two source shapes are supported:
  Format A — one row per employee/day, explicit in/out columns:
    Employee ID | Name | Date | Entry Time | Exit Time
  Format B — one row per scan event, grouped into first-in/last-out:
    Biometric ID | Date | Time | Type (IN/OUT)
The sheet is auto-detected per format by which columns are present.
Adjust COLUMN_ALIASES if a real device export uses different headers.
"""
from __future__ import annotations

import calendar
import io
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

import openpyxl
from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.core.database import get_db
from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.hr.models import (
    AttendanceImport,
    AttendanceImportRow,
    AttendanceImportStatus,
    AttendancePeriod,
    AttendancePeriodStatus,
    AttendanceRecord,
    AttendanceSource,
    AttendanceStatus,
    Employee,
    EmploymentStatus,
)
from app.hr.settings import get_settings
from app.users.models import User

# Keyword sets checked against lowercased header cells — first match wins.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "biometric_id": ("biometric id", "biometric", "employee id", "emp id", "emp code", "device id", "card no"),
    "date": ("date",),
    "entry_time": ("entry time", "in time", "check-in", "check in", "time in", "first in"),
    "exit_time": ("exit time", "out time", "check-out", "check out", "time out", "last out"),
    "time": ("time", "punch time", "timestamp"),
    "type": ("type", "in/out", "direction", "status"),
}


def _match_column(headers: list[str], key: str) -> int | None:
    aliases = COLUMN_ALIASES[key]
    for idx, h in enumerate(headers):
        h_norm = (h or "").strip().lower()
        if any(alias in h_norm for alias in aliases):
            return idx
    return None


def _parse_date_cell(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _parse_time_cell(value, on_date: date) -> datetime | None:
    """Combines a bare time-of-day cell with `on_date` into a tz-aware
    datetime. Biometric exports rarely carry a timezone — treated as the
    clinic's local wall-clock time and stored as UTC-naive-but-aware via
    a fixed offset is out of scope here; stored as-is (naive -> UTC)
    which is consistent with every other DateTime column in this app
    (server_default now() is UTC throughout)."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if isinstance(value, time):
        return datetime.combine(on_date, value, tzinfo=timezone.utc)
    if isinstance(value, str):
        for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
            try:
                t = datetime.strptime(value.strip(), fmt).time()
                return datetime.combine(on_date, t, tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


class ParsedRow(BaseModel):
    biometric_id: str
    attendance_date: date | None
    entry_time: datetime | None
    exit_time: datetime | None
    error: str | None = None


def parse_attendance_workbook(data: bytes) -> list[ParsedRow]:
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:  # openpyxl raises several distinct types for a bad file
        raise ValidationFailedError(f"Could not read the Excel file: {exc}") from None

    sheet = wb.worksheets[0]
    rows_iter = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        raise ValidationFailedError("The uploaded file has no rows.") from None
    headers = [str(c) if c is not None else "" for c in header_row]

    col_bio = _match_column(headers, "biometric_id")
    col_date = _match_column(headers, "date")
    if col_bio is None or col_date is None:
        raise ValidationFailedError(
            "Could not find an employee/biometric ID column and a date column in the sheet header. "
            f"Headers found: {headers}"
        )

    col_entry = _match_column(headers, "entry_time")
    col_exit = _match_column(headers, "exit_time")
    col_time = _match_column(headers, "time")
    col_type = _match_column(headers, "type")

    format_a = col_entry is not None or col_exit is not None
    format_b = not format_a and col_time is not None

    if not format_a and not format_b:
        raise ValidationFailedError(
            "Sheet has an ID and date column but neither Entry/Exit Time columns nor a Time+Type "
            "column pair — cannot determine attendance times."
        )

    def cell(row: tuple, idx: int | None):
        return row[idx] if idx is not None and idx < len(row) else None

    if format_a:
        parsed: list[ParsedRow] = []
        for row in rows_iter:
            bio = cell(row, col_bio)
            if bio is None or str(bio).strip() == "":
                continue
            d = _parse_date_cell(cell(row, col_date))
            entry = _parse_time_cell(cell(row, col_entry), d) if d and col_entry is not None else None
            exit_ = _parse_time_cell(cell(row, col_exit), d) if d and col_exit is not None else None
            parsed.append(ParsedRow(
                biometric_id=str(bio).strip(), attendance_date=d, entry_time=entry, exit_time=exit_,
                error=None if d else "Unrecognised or missing date",
            ))
        return parsed

    # Format B — one row per scan event; group by (biometric_id, date),
    # first scan of the day = entry, last = exit. A row's own Type column
    # is read when present but not required to decide in/out — chronological
    # min/max is more robust than trusting a free-text direction column.
    events: dict[tuple[str, date], list[datetime]] = {}
    order: list[tuple[str, date]] = []
    for row in rows_iter:
        bio = cell(row, col_bio)
        if bio is None or str(bio).strip() == "":
            continue
        d = _parse_date_cell(cell(row, col_date))
        if not d:
            continue
        t = _parse_time_cell(cell(row, col_time), d)
        if not t:
            continue
        key = (str(bio).strip(), d)
        if key not in events:
            events[key] = []
            order.append(key)
        events[key].append(t)

    return [
        ParsedRow(biometric_id=bio, attendance_date=d, entry_time=min(times), exit_time=max(times) if len(times) > 1 else None)
        for (bio, d), times in ((k, events[k]) for k in order)
    ]


def classify_status(working_minutes: int | None, *, full_day_hours: Decimal, half_day_min_hours: Decimal) -> AttendanceStatus:
    if working_minutes is None:
        return AttendanceStatus.ABSENT
    hours = Decimal(working_minutes) / Decimal(60)
    if hours >= full_day_hours:
        return AttendanceStatus.PRESENT
    if hours >= half_day_min_hours:
        return AttendanceStatus.HALF_DAY
    return AttendanceStatus.ABSENT


async def create_import(session: AsyncSession, *, filename: str, data: bytes, uploaded_by_id: uuid.UUID) -> AttendanceImport:
    parsed_rows = parse_attendance_workbook(data)

    employees = (await session.execute(select(Employee).where(Employee.biometric_id.is_not(None)))).scalars().all()
    by_bio = {e.biometric_id: e for e in employees}

    existing_records = (await session.execute(select(AttendanceRecord.employee_id, AttendanceRecord.attendance_date))).all()
    existing_keys = {(str(r[0]), r[1]) for r in existing_records}

    dated_rows = [r.attendance_date for r in parsed_rows if r.attendance_date]
    imp = AttendanceImport(
        filename=filename, uploaded_by_id=uploaded_by_id, records_found=len(parsed_rows),
        period_start=min(dated_rows) if dated_rows else None,
        period_end=max(dated_rows) if dated_rows else None,
    )
    session.add(imp)
    await session.flush()

    seen_in_file: set[tuple[str, date]] = set()
    matched = unknown = duplicate = errors = 0

    for i, row in enumerate(parsed_rows, start=1):
        employee = by_bio.get(row.biometric_id)
        is_unknown = employee is None
        working_minutes = None
        if row.entry_time and row.exit_time:
            working_minutes = int((row.exit_time - row.entry_time).total_seconds() // 60)

        file_key = (row.biometric_id, row.attendance_date) if row.attendance_date else None
        is_dup_in_file = file_key is not None and file_key in seen_in_file
        if file_key:
            seen_in_file.add(file_key)
        is_dup_existing = (
            employee is not None and row.attendance_date is not None
            and (str(employee.id), row.attendance_date) in existing_keys
        )
        is_duplicate = is_dup_in_file or is_dup_existing

        if is_unknown:
            unknown += 1
        elif is_duplicate:
            duplicate += 1
        elif row.error:
            errors += 1
        else:
            matched += 1

        session.add(AttendanceImportRow(
            import_id=imp.id, row_number=i, biometric_id=row.biometric_id,
            employee_id=employee.id if employee else None, attendance_date=row.attendance_date,
            entry_time=row.entry_time, exit_time=row.exit_time,
            is_unknown=is_unknown, is_duplicate=is_duplicate, error=row.error,
        ))

    imp.matched_count = matched
    imp.unknown_count = unknown
    imp.duplicate_count = duplicate
    imp.error_count = errors
    await session.flush()
    return imp


async def get_import(session: AsyncSession, import_id: uuid.UUID) -> AttendanceImport:
    imp = await session.get(AttendanceImport, import_id)
    if not imp:
        raise NotFoundError("Attendance import not found")
    return imp


async def list_import_rows(session: AsyncSession, import_id: uuid.UUID) -> list[AttendanceImportRow]:
    result = await session.execute(
        select(AttendanceImportRow).where(AttendanceImportRow.import_id == import_id).order_by(AttendanceImportRow.row_number)
    )
    return list(result.scalars().all())


async def confirm_import(session: AsyncSession, import_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str) -> AttendanceImport:
    imp = await get_import(session, import_id)
    if imp.status == AttendanceImportStatus.CONFIRMED:
        raise ValidationFailedError("This import has already been confirmed.")

    settings = await get_settings(session)
    rows = await list_import_rows(session, import_id)

    existing = (await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.employee_id.in_([r.employee_id for r in rows if r.employee_id])
        )
    )).scalars().all()
    existing_by_key = {(r.employee_id, r.attendance_date): r for r in existing}

    written = 0
    for row in rows:
        if row.is_unknown or row.error or not row.employee_id or not row.attendance_date:
            continue  # unknown IDs and unparseable rows never become AttendanceRecord — reviewable only via the import's own row list

        working_minutes = None
        if row.entry_time and row.exit_time:
            working_minutes = int((row.exit_time - row.entry_time).total_seconds() // 60)
        status = classify_status(
            working_minutes,
            full_day_hours=Decimal(str(settings.full_day_hours)),
            half_day_min_hours=Decimal(str(settings.half_day_min_hours)),
        )

        key = (row.employee_id, row.attendance_date)
        existing_record = existing_by_key.get(key)
        if existing_record:
            # Idempotent overwrite — same employee+date seen again (re-upload
            # of a corrected file, or a duplicate row within this file)
            # updates in place instead of erroring or duplicating.
            existing_record.entry_time = row.entry_time
            existing_record.exit_time = row.exit_time
            existing_record.working_minutes = working_minutes
            existing_record.status = status
            existing_record.source = AttendanceSource.BIOMETRIC_IMPORT
            existing_record.import_id = imp.id
            existing_record.missing_entry = row.entry_time is None
            existing_record.missing_exit = row.exit_time is None
        else:
            new_record = AttendanceRecord(
                employee_id=row.employee_id, attendance_date=row.attendance_date,
                entry_time=row.entry_time, exit_time=row.exit_time, working_minutes=working_minutes,
                status=status, source=AttendanceSource.BIOMETRIC_IMPORT, import_id=imp.id,
                missing_entry=row.entry_time is None, missing_exit=row.exit_time is None,
            )
            session.add(new_record)
            existing_by_key[key] = new_record
        written += 1

    imp.status = AttendanceImportStatus.CONFIRMED
    imp.confirmed_at = datetime.now(timezone.utc)
    imp.confirmed_by_id = actor_id
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="hr.attendance_import_confirmed", entity_type="AttendanceImport", entity_id=str(imp.id),
        after_state={"records_written": written, "filename": imp.filename},
    )
    return imp


async def list_attendance(
    session: AsyncSession, *, from_date: date | None, to_date: date | None,
    department: str | None, employee_id: uuid.UUID | None, status: AttendanceStatus | None,
) -> list[AttendanceRecord]:
    stmt = select(AttendanceRecord, Employee).join(Employee, Employee.id == AttendanceRecord.employee_id)
    if from_date:
        stmt = stmt.where(AttendanceRecord.attendance_date >= from_date)
    if to_date:
        stmt = stmt.where(AttendanceRecord.attendance_date <= to_date)
    if department:
        stmt = stmt.where(Employee.department == department)
    if employee_id:
        stmt = stmt.where(AttendanceRecord.employee_id == employee_id)
    if status:
        stmt = stmt.where(AttendanceRecord.status == status)
    stmt = stmt.order_by(AttendanceRecord.attendance_date.desc())
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def resolve_attendance_issue(session: AsyncSession, record_id: uuid.UUID, *, actor_id: uuid.UUID) -> AttendanceRecord:
    record = await session.get(AttendanceRecord, record_id)
    if not record:
        raise NotFoundError("Attendance record not found")
    record.resolved_at = datetime.now(timezone.utc)
    record.resolved_by_id = actor_id
    await session.flush()
    return record


# --------------------------------------------------------------------------- #
# Monthly ledger — the shared "what actually happened this month" view that
# both the Monthly Attendance screen and payroll calculation read from, so
# the two can never disagree about present/half/absent/unprocessed counts.
# --------------------------------------------------------------------------- #

class DayLedgerEntry(BaseModel):
    date: date
    is_working_day: bool  # false for Sundays and for dates still in the future
    status: AttendanceStatus | None  # None = no record for this day


class EmployeeMonthLedger(BaseModel):
    employee_id: uuid.UUID
    working_days: int        # candidate working days (not Sunday, not future) in the month up to today
    processed_days: int      # of those, how many have an AttendanceRecord
    unprocessed_days: int
    present_days: int        # ALL present-status records in the month (may include a worked Sunday — a real bonus day, not capped by working_days)
    half_days: int
    absent_days: int
    days: list[DayLedgerEntry]


def _month_bounds(month: int, year: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


async def compute_employee_month_ledger(session: AsyncSession, employee_id: uuid.UUID, month: int, year: int) -> EmployeeMonthLedger:
    start, end = _month_bounds(month, year)
    today = datetime.now(timezone.utc).date()

    records = (await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.attendance_date >= start,
            AttendanceRecord.attendance_date <= end,
        )
    )).scalars().all()
    by_date = {r.attendance_date: r for r in records}

    days: list[DayLedgerEntry] = []
    working_days = processed_days = 0
    d = start
    while d <= end:
        # Sunday (weekday() == 6) is treated as the clinic's weekly off —
        # not counted toward working days at all, present or absent. A
        # date still in the future hasn't happened yet, so it can't be
        # "unprocessed" either — it's simply not applicable yet. Neither
        # rule is configurable today (no holiday-calendar model exists in
        # this codebase); see HrSettings for where to extend this if a
        # real holiday list is added later.
        is_working_day = d.weekday() != 6 and d <= today
        record = by_date.get(d)
        if is_working_day:
            working_days += 1
            if record:
                processed_days += 1
        days.append(DayLedgerEntry(date=d, is_working_day=is_working_day, status=record.status if record else None))
        d = date.fromordinal(d.toordinal() + 1)

    present_days = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    half_days = sum(1 for r in records if r.status == AttendanceStatus.HALF_DAY)
    absent_days = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)

    return EmployeeMonthLedger(
        employee_id=employee_id, working_days=working_days, processed_days=processed_days,
        unprocessed_days=max(0, working_days - processed_days),
        present_days=present_days, half_days=half_days, absent_days=absent_days, days=days,
    )


async def get_monthly_grid(
    session: AsyncSession, *, month: int, year: int, department: str | None = None, employee_id: uuid.UUID | None = None,
) -> list[tuple[Employee, EmployeeMonthLedger]]:
    stmt = select(Employee).where(Employee.employment_status == EmploymentStatus.ACTIVE)
    if department:
        stmt = stmt.where(Employee.department == department)
    if employee_id:
        stmt = stmt.where(Employee.id == employee_id)
    stmt = stmt.order_by(Employee.full_name)
    employees = (await session.execute(stmt)).scalars().all()
    return [(e, await compute_employee_month_ledger(session, e.id, month, year)) for e in employees]


async def get_period(session: AsyncSession, month: int, year: int) -> AttendancePeriod:
    period = (await session.execute(
        select(AttendancePeriod).where(AttendancePeriod.month == month, AttendancePeriod.year == year)
    )).scalar_one_or_none()
    if not period:
        period = AttendancePeriod(month=month, year=year)
        session.add(period)
        await session.flush()
    return period


async def finalize_period(
    session: AsyncSession, month: int, year: int, *, override: bool, reason: str | None, actor_id: uuid.UUID, actor_role: str,
) -> AttendancePeriod:
    period = await get_period(session, month, year)
    if period.status == AttendancePeriodStatus.FINALIZED:
        raise ConflictError("This attendance period is already finalized.")

    ledgers = await get_monthly_grid(session, month=month, year=year)
    total_unprocessed = sum(l.unprocessed_days for _, l in ledgers)
    if total_unprocessed > 0 and not override:
        raise ConflictError(
            f"{total_unprocessed} working day(s) across active employees have not been processed yet. "
            "Import the missing attendance, or finalize with an override and a reason.",
            error_code="attendance_incomplete",
        )
    if total_unprocessed > 0 and override and not (reason and reason.strip()):
        raise ValidationFailedError("A reason is required to finalize with unprocessed attendance remaining.")

    period.status = AttendancePeriodStatus.FINALIZED
    period.finalized_at = datetime.now(timezone.utc)
    period.finalized_by_id = actor_id
    period.override_used = total_unprocessed > 0 and override
    period.override_reason = reason if period.override_used else None
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role, action="hr.attendance_period_finalized",
        entity_type="AttendancePeriod", entity_id=str(period.id),
        after_state={"month": month, "year": year, "unprocessed_days": total_unprocessed, "override_used": period.override_used},
        reason=reason,
    )
    return period


async def reopen_period(session: AsyncSession, month: int, year: int, *, actor_id: uuid.UUID, actor_role: str) -> AttendancePeriod:
    period = await get_period(session, month, year)
    if period.status != AttendancePeriodStatus.FINALIZED:
        raise ConflictError("This attendance period is not finalized.")
    period.status = AttendancePeriodStatus.OPEN
    period.finalized_at = None
    period.finalized_by_id = None
    period.override_used = False
    period.override_reason = None
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role, action="hr.attendance_period_reopened",
        entity_type="AttendancePeriod", entity_id=str(period.id), after_state={"month": month, "year": year},
    )
    return period


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class AttendanceImportRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    row_number: int
    biometric_id: str
    employee_id: uuid.UUID | None
    attendance_date: date | None
    entry_time: datetime | None
    exit_time: datetime | None
    is_unknown: bool
    is_duplicate: bool
    error: str | None


class AttendanceImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str
    status: AttendanceImportStatus
    records_found: int
    matched_count: int
    unknown_count: int
    duplicate_count: int
    error_count: int
    period_start: date | None
    period_end: date | None
    created_at: datetime
    confirmed_at: datetime | None


class AttendanceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: uuid.UUID
    attendance_date: date
    entry_time: datetime | None
    exit_time: datetime | None
    working_minutes: int | None
    status: AttendanceStatus
    source: AttendanceSource
    missing_entry: bool
    missing_exit: bool
    resolved_at: datetime | None


class MonthlyAttendanceRowOut(BaseModel):
    employee_id: uuid.UUID
    full_name: str
    department: str
    days: dict[int, str | None]  # day-of-month -> "P"/"HD"/"A"/None (no record); non-working days simply absent from the dict... actually always present, see service
    working_days: int
    processed_days: int
    unprocessed_days: int
    present_days: int
    half_days: int
    absent_days: int
    attendance_percent: float
    is_complete: bool


class AttendancePeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    month: int
    year: int
    status: AttendancePeriodStatus
    finalized_at: datetime | None
    finalized_by_id: uuid.UUID | None
    override_used: bool
    override_reason: str | None


class PeriodSummaryOut(BaseModel):
    period: AttendancePeriodOut
    working_days: int
    processed_days: int
    unprocessed_days: int
    present_days: int
    half_days: int
    absent_days: int
    employee_count: int


class FinalizePeriodRequest(BaseModel):
    override: bool = False
    reason: str | None = None


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #

router = APIRouter(prefix="/hr/attendance", tags=["hr-attendance"])


@router.post("/imports", response_model=AttendanceImportOut, status_code=201)
async def upload_attendance_import(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.attendance_import")),
) -> AttendanceImportOut:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise ValidationFailedError("Only .xlsx or .xls files are accepted.")
    if file.filename.lower().endswith(".xls"):
        raise ValidationFailedError("Legacy .xls is not supported — please export as .xlsx.")
    data = await file.read()
    imp = await create_import(session, filename=file.filename, data=data, uploaded_by_id=current.id)
    return imp


@router.get("/imports/{import_id}", response_model=AttendanceImportOut)
async def get_attendance_import(
    import_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.attendance_read")),
) -> AttendanceImportOut:
    return await get_import(session, import_id)


@router.get("/imports/{import_id}/rows", response_model=list[AttendanceImportRowOut])
async def get_attendance_import_rows(
    import_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.attendance_read")),
) -> list[AttendanceImportRowOut]:
    return await list_import_rows(session, import_id)


@router.post("/imports/{import_id}/confirm", response_model=AttendanceImportOut)
async def confirm_attendance_import(
    import_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.attendance_import")),
) -> AttendanceImportOut:
    return await confirm_import(session, import_id, actor_id=current.id, actor_role=current.role.code)


@router.get("/records", response_model=list[AttendanceRecordOut])
async def list_attendance_records(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    department: str | None = Query(default=None),
    employee_id: uuid.UUID | None = Query(default=None),
    status: AttendanceStatus | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.attendance_read")),
) -> list[AttendanceRecordOut]:
    return await list_attendance(session, from_date=from_date, to_date=to_date, department=department, employee_id=employee_id, status=status)


@router.get("/issues", response_model=list[AttendanceRecordOut])
async def list_attendance_issues(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.attendance_read")),
) -> list[AttendanceRecordOut]:
    """Unresolved anomalies — spec §7: missing entry/exit. Duplicate/unknown
    rows never reach AttendanceRecord (see confirm_import), so those are
    reviewed on the import's own row list instead."""
    stmt = select(AttendanceRecord).where(
        AttendanceRecord.resolved_at.is_(None),
        (AttendanceRecord.missing_entry.is_(True)) | (AttendanceRecord.missing_exit.is_(True)),
    ).order_by(AttendanceRecord.attendance_date.desc())
    return list((await session.execute(stmt)).scalars().all())


@router.post("/records/{record_id}/resolve", response_model=AttendanceRecordOut)
async def resolve_attendance_record(
    record_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.attendance_import")),
) -> AttendanceRecordOut:
    return await resolve_attendance_issue(session, record_id, actor_id=current.id)


_STATUS_CODE = {AttendanceStatus.PRESENT: "P", AttendanceStatus.HALF_DAY: "HD", AttendanceStatus.ABSENT: "A"}


def _ledger_to_row(employee: Employee, ledger: EmployeeMonthLedger) -> MonthlyAttendanceRowOut:
    days: dict[int, str | None] = {}
    for entry in ledger.days:
        if entry.status is not None:
            days[entry.date.day] = _STATUS_CODE[entry.status]
        elif entry.is_working_day:
            days[entry.date.day] = "?"  # working day, no attendance data yet
        else:
            days[entry.date.day] = None  # Sunday / future — not applicable, rendered "—"
    attendance_percent = round(100 * (ledger.present_days + ledger.half_days * 0.5) / ledger.working_days, 1) if ledger.working_days else 0.0
    return MonthlyAttendanceRowOut(
        employee_id=employee.id, full_name=employee.full_name, department=employee.department,
        days=days, working_days=ledger.working_days, processed_days=ledger.processed_days,
        unprocessed_days=ledger.unprocessed_days, present_days=ledger.present_days, half_days=ledger.half_days,
        absent_days=ledger.absent_days, attendance_percent=attendance_percent, is_complete=ledger.unprocessed_days == 0,
    )


@router.get("/monthly", response_model=list[MonthlyAttendanceRowOut])
async def get_monthly_attendance(
    month: int = Query(...),
    year: int = Query(...),
    department: str | None = Query(default=None),
    employee_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.attendance_read")),
) -> list[MonthlyAttendanceRowOut]:
    ledgers = await get_monthly_grid(session, month=month, year=year, department=department, employee_id=employee_id)
    return [_ledger_to_row(e, l) for e, l in ledgers]


@router.get("/periods/{year}/{month}", response_model=PeriodSummaryOut)
async def get_period_summary(
    year: int, month: int,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.attendance_read")),
) -> PeriodSummaryOut:
    period = await get_period(session, month, year)
    ledgers = await get_monthly_grid(session, month=month, year=year)
    return PeriodSummaryOut(
        period=AttendancePeriodOut.model_validate(period),
        working_days=sum(l.working_days for _, l in ledgers),
        processed_days=sum(l.processed_days for _, l in ledgers),
        unprocessed_days=sum(l.unprocessed_days for _, l in ledgers),
        present_days=sum(l.present_days for _, l in ledgers),
        half_days=sum(l.half_days for _, l in ledgers),
        absent_days=sum(l.absent_days for _, l in ledgers),
        employee_count=len(ledgers),
    )


@router.post("/periods/{year}/{month}/finalize", response_model=AttendancePeriodOut)
async def finalize_period_endpoint(
    year: int, month: int, body: FinalizePeriodRequest,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.attendance_finalize")),
) -> AttendancePeriodOut:
    period = await finalize_period(
        session, month, year, override=body.override, reason=body.reason, actor_id=current.id, actor_role=current.role.code,
    )
    return AttendancePeriodOut.model_validate(period)


@router.post("/periods/{year}/{month}/reopen", response_model=AttendancePeriodOut)
async def reopen_period_endpoint(
    year: int, month: int,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.attendance_finalize")),
) -> AttendancePeriodOut:
    period = await reopen_period(session, month, year, actor_id=current.id, actor_role=current.role.code)
    return AttendancePeriodOut.model_validate(period)

"""Employee directory, leave, attendance — spec §24. Deliberately kept
distinct from `users` (login accounts): not every employee needs system
access (e.g. housekeeping staff), and not every system user is tracked
here in the same HR sense (though most will have both records linked)."""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EmploymentStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Employee(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "employees"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Free text, not an FK/enum — no Department model exists in this
    # codebase (confirmed: every module that has a "department" concept,
    # e.g. users.department, stores it as a plain string). Keeping this
    # consistent with the rest of the app rather than introducing the
    # first normalized Department table for HR alone.
    department: Mapped[str] = mapped_column(String(128), nullable=False)
    designation: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    joined_date: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True)
    leave_balance_days: Mapped[int] = mapped_column(Integer, default=18)

    employment_status: Mapped[EmploymentStatus] = mapped_column(Enum(EmploymentStatus), default=EmploymentStatus.ACTIVE, index=True)
    # Rupees, not paise — matches Employee-facing "₹30,000/month" input
    # rather than the paise-everywhere convention billing/pharmacy use for
    # transaction amounts; payroll math converts to paise internally (see
    # app/hr/payroll.py) to avoid float rounding on the final payable figure.
    monthly_salary_rupees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    working_hours_per_day: Mapped[int] = mapped_column(Integer, default=8)  # for display only; HrSettings drives the actual thresholds
    # The ID string the biometric device prints/exports — distinct from
    # this row's own UUID PK. Unique so an attendance import can look an
    # employee up by it unambiguously; nullable because not every employee
    # is enrolled on the biometric device on day one.
    biometric_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)


class LeaveRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "leave_requests"

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    leave_type: Mapped[str] = mapped_column(String(64), nullable=False)  # Sick, Casual, Annual
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[LeaveStatus] = mapped_column(Enum(LeaveStatus), default=LeaveStatus.PENDING, index=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    HALF_DAY = "half_day"
    ABSENT = "absent"


class AttendanceSource(str, enum.Enum):
    MANUAL = "manual"
    BIOMETRIC_IMPORT = "biometric_import"


class AttendanceRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per employee per day. `entry_time`/`exit_time` are the
    first-in/last-out timestamps for that day (already reduced from
    possibly-many raw biometric scans — see AttendanceImportRow for the
    raw rows an import staged before this table was written to).
    `(employee_id, attendance_date)` is unique so importing the same
    biometric file twice, or re-uploading a corrected file for a date
    already recorded, updates the existing row instead of duplicating it —
    the idempotent-import guarantee spec §20/§21 asks for."""
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("employee_id", "attendance_date", name="uq_attendance_employee_date"),)

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    entry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    working_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus), nullable=False, index=True)
    source: Mapped[AttendanceSource] = mapped_column(Enum(AttendanceSource), default=AttendanceSource.MANUAL)
    import_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_imports.id"), nullable=True)

    # Anomaly flags spec §7 asks HR to be able to review — set at
    # calculation time, cleared once HR resolves the record manually.
    missing_entry: Mapped[bool] = mapped_column(Boolean, default=False)
    missing_exit: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class AttendanceImportStatus(str, enum.Enum):
    PREVIEWED = "previewed"  # parsed, staged in AttendanceImportRow, awaiting HR confirmation
    CONFIRMED = "confirmed"  # rows written into AttendanceRecord


class AttendanceImport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per uploaded biometric Excel file. Rows are staged into
    AttendanceImportRow at upload time (parse only, no AttendanceRecord
    writes yet) so HR can review the preview — records found, matched,
    unknown IDs, duplicates — before confirming spec §21's two-step
    import safety flow."""
    __tablename__ = "attendance_imports"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[AttendanceImportStatus] = mapped_column(Enum(AttendanceImportStatus), default=AttendanceImportStatus.PREVIEWED, index=True)

    records_found: Mapped[int] = mapped_column(Integer, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    unknown_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    # The file may cover one day or an entire month (spec: "do not assume
    # one uploaded file represents only one day") — min/max of the parsed
    # rows' dates, shown on the preview so HR sees what range they're
    # actually importing before confirming.
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class AttendanceImportRow(Base, UUIDPrimaryKeyMixin):
    """One staged row per employee+date extracted from the uploaded file
    (already reduced from raw scans to first-in/last-out if the source
    format was scan-event-per-row — see app/hr/attendance.py's parser).
    Kept even after confirmation as the import's own audit trail of
    exactly what was in the file, independent of whatever the
    AttendanceRecord it produced is later edited to."""
    __tablename__ = "attendance_import_rows"

    import_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_imports.id"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    biometric_id: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True)
    attendance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    entry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_unknown: Mapped[bool] = mapped_column(Boolean, default=False)  # biometric_id matched no Employee
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)  # same employee+date already elsewhere in this file
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AttendancePeriodStatus(str, enum.Enum):
    OPEN = "open"
    FINALIZED = "finalized"


class AttendancePeriod(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per (month, year) — whether that month's attendance has
    been reviewed and finalized by HR. Payroll for a month may be
    *calculated* at any time (so HR can preview numbers mid-month), but
    stays in PayrollStatus.DRAFT — not approvable — until this period is
    FINALIZED, per the "don't allow approval on incomplete attendance"
    rule. Finalizing with unprocessed working days remaining requires an
    explicit override + reason, recorded here for audit."""
    __tablename__ = "hr_attendance_periods"
    __table_args__ = (UniqueConstraint("month", "year", name="uq_attendance_period_month_year"),)

    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AttendancePeriodStatus] = mapped_column(Enum(AttendancePeriodStatus), default=AttendancePeriodStatus.OPEN, index=True)

    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    override_used: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

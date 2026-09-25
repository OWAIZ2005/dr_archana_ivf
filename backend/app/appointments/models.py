"""
Appointment + patient status flow, from the frontend's BookingSlot shape
and spec §12's queue:
  Registered -> Arrived -> Waiting -> Consultation -> Investigation/Scan/
  Procedure -> Billing -> Pharmacy -> Follow-up -> Completed
"""
import enum
import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class AppointmentChannel(str, enum.Enum):
    WALK_IN = "walk_in"
    ONLINE = "online"
    PHONE = "phone"


class AppointmentStatus(str, enum.Enum):
    REGISTERED = "registered"
    ARRIVED = "arrived"
    WAITING = "waiting"
    CONSULTATION = "consultation"
    INVESTIGATION = "investigation"
    BILLING = "billing"
    PHARMACY = "pharmacy"
    FOLLOW_UP = "follow_up"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


# The only status transitions the workflow engine allows — enforced in
# service.py, not just documented. Authorized emergency overrides bypass
# this via a separate, audited code path (see workflow engine, Phase 3).
ALLOWED_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.REGISTERED: {AppointmentStatus.ARRIVED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW},
    # COMPLETED is reachable directly from ARRIVED, not only through the
    # granular WAITING -> ... -> PHARMACY/FOLLOW_UP chain below: the
    # front-desk and prescription-department workflow this actually
    # supports today is "patient arrives, is seen, prescription is
    # dispensed, done" — there is no UI yet driving the intermediate
    # consultation/investigation/billing states, so requiring a visit to
    # pass through all of them before it could ever be closed out would
    # make every real appointment un-completable.
    AppointmentStatus.ARRIVED: {AppointmentStatus.WAITING, AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED},
    AppointmentStatus.WAITING: {AppointmentStatus.CONSULTATION, AppointmentStatus.CANCELLED},
    AppointmentStatus.CONSULTATION: {AppointmentStatus.INVESTIGATION, AppointmentStatus.BILLING, AppointmentStatus.FOLLOW_UP},
    AppointmentStatus.INVESTIGATION: {AppointmentStatus.BILLING, AppointmentStatus.CONSULTATION},
    AppointmentStatus.BILLING: {AppointmentStatus.PHARMACY, AppointmentStatus.FOLLOW_UP, AppointmentStatus.COMPLETED},
    AppointmentStatus.PHARMACY: {AppointmentStatus.FOLLOW_UP, AppointmentStatus.COMPLETED},
    AppointmentStatus.FOLLOW_UP: {AppointmentStatus.COMPLETED},
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.CANCELLED: set(),
    AppointmentStatus.NO_SHOW: set(),
}


class Appointment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "appointments"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    visit_type: Mapped[str] = mapped_column(String(128), nullable=False)  # "Follicle Monitoring", "IVF Consultation", ...
    channel: Mapped[AppointmentChannel] = mapped_column(Enum(AppointmentChannel), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.REGISTERED, index=True
    )

    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Front desk clicked "Not Arrived" — a soft, reversible flag distinct
    # from the terminal NO_SHOW status. Status stays REGISTERED while this
    # is set, so "Mark Arrived" still works normally; the frontend shows a
    # yellow countdown from this timestamp and, once NOT_ARRIVED_GRACE_PERIOD
    # has elapsed with still no arrival, prompts staff to reschedule instead
    # of silently leaving the appointment in limbo. Cleared automatically
    # the moment the patient actually checks in (see transition_status).
    marked_not_arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Free-text notes — used by the Phone Call Appointment form's
    # "Description" field, and generally available for any appointment.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # A human-facing daily queue number, assigned once at booking time and
    # never reused/renumbered — see service._next_token_number. Distinct
    # from the DB id: staff call out "Token 7", not a UUID.
    token_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Resolved once at create/reschedule time from AppointmentBatch's
    # (start_time, end_time, visit_types) against this appointment's own
    # scheduled_at/visit_type — see service.resolve_batch. Null means no
    # configured batch currently covers this slot/visit type; the
    # front-desk dashboard groups those under an "Unbatched" bucket rather
    # than failing the booking, since batch config is meant to evolve
    # independently of what can be booked.
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointment_batches.id"), nullable=True, index=True)


class AppointmentBatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A configurable front-desk time slot (e.g. "09:00-10:00 AM —
    ANC/CD/RD"). Appointment placement is computed from scheduled_at's time
    plus visit_type against these rows, not hardcoded in the frontend —
    per the hospital's requirement that batch definitions themselves
    change over time without a code deploy. `visit_types` is a
    comma-separated list of the free-text visit_type values this batch
    accepts (matched case-insensitively); the same visit_type (e.g. "CD")
    may legitimately appear in more than one batch, since the correct
    batch for a given appointment also depends on its scheduled time."""
    __tablename__ = "appointment_batches"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    visit_types: Mapped[str] = mapped_column(String(500), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    # Max appointments this batch accepts on a single day; null = unlimited.
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AppointmentHistory(Base, UUIDPrimaryKeyMixin):
    """Immutable audit trail for reschedules — the live Appointment row is
    always mutated in place (so every other query keeps working
    unchanged), but every reschedule appends one row here preserving the
    prior date/time/status rather than silently overwriting it."""
    __tablename__ = "appointment_history"

    appointment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True)
    old_scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    new_scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReminderStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Reminder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A front-desk follow-up task against a patient (optionally tied to a
    specific appointment) — e.g. "call about rescheduling", "confirm
    tomorrow's fasting instructions". Deliberately its own lightweight
    entity rather than overloading Appointment.notes, since a reminder has
    its own due date and lifecycle independent of any single visit."""
    __tablename__ = "reminders"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True, index=True)

    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[ReminderStatus] = mapped_column(Enum(ReminderStatus), nullable=False, default=ReminderStatus.PENDING, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    completed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CommunicationChannel(str, enum.Enum):
    CALL = "call"
    EMAIL = "email"


# A fixed, validated set of outcomes — free text would make the "why did
# we contact this patient" history impossible to report on later.
COMMUNICATION_OUTCOMES = [
    "Patient will attend later",
    "Patient requested rescheduling",
    "Patient cancelled",
    "Unable to reach",
    "Patient confirmed attendance",
    "Other",
]


class PatientCommunication(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A record of a front-desk contact attempt — call or email — usually
    prompted by a late/no-show appointment. Never claims a call actually
    connected; it records that a staff member initiated contact and what
    they learned, per the "do not pretend a call happened" requirement."""
    __tablename__ = "patient_communications"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True, index=True)

    channel: Mapped[CommunicationChannel] = mapped_column(Enum(CommunicationChannel), nullable=False)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contacted_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    contacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

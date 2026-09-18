import uuid
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.appointments.models import (
    ALLOWED_TRANSITIONS,
    Appointment,
    AppointmentBatch,
    AppointmentHistory,
    AppointmentStatus,
)
from app.appointments.schemas import AppointmentCreate, AppointmentListParams
from app.audit.service import record_audit_event
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.events.bus import EventType, emit
from app.patients.models import Patient


HOSPITAL_TIMEZONE = ZoneInfo("Asia/Kolkata")

# An appointment in either of these statuses no longer occupies its slot —
# excluded from both capacity counts and the "booked" figure shown to staff.
_INACTIVE_STATUSES = (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW)


def _local_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """The hospital's own calendar day (IST), expressed as a UTC range —
    the one place "what day is this appointment on" is computed, so
    booking/listing/token-numbering/capacity all agree with each other
    and with what front-desk staff mean by "today"."""
    start_local = datetime.combine(day, datetime.min.time(), tzinfo=HOSPITAL_TIMEZONE)
    end_local = datetime.combine(day, datetime.max.time(), tzinfo=HOSPITAL_TIMEZONE)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


async def _next_token_number(session: AsyncSession, *, scheduled_at: datetime) -> int:
    """A daily queue number, 1-based and never reused, scoped to the
    hospital's local calendar day (not the batch) — matches how a real
    front desk calls out "Token 7" regardless of which doctor/batch."""
    local_day = scheduled_at.astimezone(HOSPITAL_TIMEZONE).date()
    start_utc, end_utc = _local_day_bounds_utc(local_day)
    result = await session.execute(
        select(func.max(Appointment.token_number)).where(
            Appointment.scheduled_at >= start_utc, Appointment.scheduled_at < end_utc,
        )
    )
    last = result.scalar_one_or_none()
    return (last or 0) + 1


async def _batch_booked_count(
    session: AsyncSession, batch_id: uuid.UUID, *, day: date, exclude_appointment_id: uuid.UUID | None = None
) -> int:
    start_utc, end_utc = _local_day_bounds_utc(day)
    stmt = select(func.count(Appointment.id)).where(
        Appointment.batch_id == batch_id,
        Appointment.scheduled_at >= start_utc, Appointment.scheduled_at < end_utc,
        Appointment.status.notin_(_INACTIVE_STATUSES),
    )
    if exclude_appointment_id is not None:
        stmt = stmt.where(Appointment.id != exclude_appointment_id)
    return (await session.execute(stmt)).scalar_one()


async def _enforce_batch_capacity(
    session: AsyncSession, batch: AppointmentBatch | None, *, scheduled_at: datetime, exclude_appointment_id: uuid.UUID | None = None
) -> None:
    if batch is None or batch.capacity is None:
        return
    local_day = scheduled_at.astimezone(HOSPITAL_TIMEZONE).date()
    booked = await _batch_booked_count(session, batch.id, day=local_day, exclude_appointment_id=exclude_appointment_id)
    if booked >= batch.capacity:
        raise ConflictError(
            f"'{batch.name}' is fully booked for this day ({booked}/{batch.capacity}). Please choose another slot.",
            error_code="batch_full",
        )


async def resolve_batch(session: AsyncSession, *, scheduled_at: datetime, visit_type: str) -> AppointmentBatch | None:
    """Finds the configured AppointmentBatch (if any) whose time window
    covers `scheduled_at` and whose visit_types list contains `visit_type`
    (case-insensitive). The same visit_type can appear in more than one
    batch (e.g. "CD" in both a morning and an evening batch) — time is
    what disambiguates them, so this always checks both together.

    Batch start/end times are configured in the hospital's own local time
    (IST), while scheduled_at is stored tz-aware (typically UTC) — always
    convert here rather than comparing raw clock values, so this is the
    one place hospital-timezone handling lives instead of scattering it
    across callers."""
    local_time = scheduled_at.astimezone(HOSPITAL_TIMEZONE).time()
    result = await session.execute(
        select(AppointmentBatch).where(AppointmentBatch.is_active.is_(True)).order_by(AppointmentBatch.display_order)
    )
    needle = visit_type.strip().lower()
    for batch in result.scalars().all():
        if not (batch.start_time <= local_time < batch.end_time):
            continue
        types = {v.strip().lower() for v in batch.visit_types.split(",") if v.strip()}
        if needle in types:
            return batch
    return None


async def create_appointment(session: AsyncSession, data: AppointmentCreate) -> Appointment:
    batch = await resolve_batch(session, scheduled_at=data.scheduled_at, visit_type=data.visit_type)
    await _enforce_batch_capacity(session, batch, scheduled_at=data.scheduled_at)
    token_number = await _next_token_number(session, scheduled_at=data.scheduled_at)
    appt = Appointment(**data.model_dump(), batch_id=batch.id if batch else None, token_number=token_number)
    session.add(appt)
    await session.flush()
    return appt


async def get_appointment(session: AsyncSession, appointment_id: uuid.UUID) -> Appointment:
    appt = await session.get(Appointment, appointment_id)
    if not appt:
        raise NotFoundError("Appointment not found", error_code="appointment_not_found")
    return appt


async def list_appointments_for_day(
    session: AsyncSession, *, day: date, doctor_id: uuid.UUID | None = None, status: AppointmentStatus | None = None
) -> list[Appointment]:
    start_utc, end_utc = _local_day_bounds_utc(day)
    stmt = select(Appointment).where(Appointment.scheduled_at >= start_utc, Appointment.scheduled_at < end_utc)
    if doctor_id:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    if status:
        stmt = stmt.where(Appointment.status == status)
    result = await session.execute(stmt.order_by(Appointment.scheduled_at))
    return list(result.scalars().all())


async def list_appointments_for_patient(
    session: AsyncSession, patient_id: uuid.UUID, *, limit: int = 50
) -> list[Appointment]:
    """A patient's appointments, most recent first. Used by clinical screens
    (e.g. nursing records) to let staff link a record to the visit it was
    taken during."""
    result = await session.execute(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .order_by(Appointment.scheduled_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def transition_status(
    session: AsyncSession,
    appointment_id: uuid.UUID,
    new_status: AppointmentStatus,
    *,
    actor_id: uuid.UUID,
    actor_role: str,
    reason: str | None = None,
) -> Appointment:
    """The workflow-enforced status transition — this is the server-side
    guarantee behind spec §12: "This must be workflow-driven, not merely
    visual." A frontend calling this endpoint with an illegal transition
    gets a 409, not a silently-accepted status flip."""
    appt = await get_appointment(session, appointment_id)

    allowed = ALLOWED_TRANSITIONS.get(appt.status, set())
    if new_status not in allowed:
        raise ConflictError(
            f"Cannot move appointment from '{appt.status.value}' to '{new_status.value}'.",
            error_code="illegal_status_transition",
        )

    if new_status in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW) and not reason:
        raise ValidationFailedError("A reason is required to cancel or mark a no-show.")

    before_status = appt.status
    now = datetime.now(timezone.utc)

    appt.status = new_status
    if new_status == AppointmentStatus.ARRIVED:
        appt.checked_in_at = now
        appt.marked_not_arrived_at = None
    if new_status == AppointmentStatus.COMPLETED:
        appt.completed_at = now
    if new_status in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW):
        appt.cancellation_reason = reason

    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="appointment.status_changed", entity_type="Appointment", entity_id=str(appt.id),
        before_state={"status": before_status.value}, after_state={"status": new_status.value}, reason=reason,
    )

    if new_status == AppointmentStatus.ARRIVED:
        await emit(
            session, event_type=EventType.APPOINTMENT_CHECKED_IN,
            entity_type="Appointment", entity_id=str(appt.id),
            payload={"patient_id": str(appt.patient_id), "doctor_id": str(appt.doctor_id)},
        )
    if new_status == AppointmentStatus.CANCELLED:
        await emit(
            session, event_type=EventType.APPOINTMENT_CANCELLED,
            entity_type="Appointment", entity_id=str(appt.id),
            payload={"reason": reason},
        )

    return appt


# How long a "Not Arrived" flag sits in the yellow/awaiting state before the
# frontend nudges staff to reschedule instead of leaving it open-ended.
NOT_ARRIVED_GRACE_PERIOD_MINUTES = 120


async def mark_not_arrived(
    session: AsyncSession, appointment_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str
) -> Appointment:
    """A soft, reversible flag — unlike transition_status(NO_SHOW), this
    does NOT change the appointment's status or require a reason. The
    appointment stays REGISTERED (so "Mark Arrived" keeps working) while
    the frontend shows a yellow countdown from this timestamp. Only after
    NOT_ARRIVED_GRACE_PERIOD_MINUTES with no arrival does staff get
    prompted to actually reschedule or finalize as NO_SHOW."""
    appt = await get_appointment(session, appointment_id)
    if appt.status != AppointmentStatus.REGISTERED:
        raise ConflictError(f"Cannot mark not-arrived for an appointment in status '{appt.status.value}'.", error_code="illegal_not_arrived")

    appt.marked_not_arrived_at = datetime.now(timezone.utc)
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="appointment.marked_not_arrived", entity_type="Appointment", entity_id=str(appt.id),
    )
    return appt


async def clear_not_arrived(
    session: AsyncSession, appointment_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str
) -> Appointment:
    """Undoes mark_not_arrived — the patient turned out to be present, or
    staff clicked it by mistake."""
    appt = await get_appointment(session, appointment_id)
    appt.marked_not_arrived_at = None
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="appointment.not_arrived_cleared", entity_type="Appointment", entity_id=str(appt.id),
    )
    return appt


async def edit_appointment(
    session: AsyncSession, appointment_id: uuid.UUID, data, *, actor_id: uuid.UUID, actor_role: str
) -> Appointment:
    """Fixes a booking mistake (wrong visit type/doctor) in place — date
    and time are untouched (use reschedule_appointment for that). Only
    allowed while REGISTERED, same as reschedule. If visit_type changes,
    the batch is re-resolved for the appointment's existing scheduled_at
    and the new batch's capacity is enforced."""
    appt = await get_appointment(session, appointment_id)
    if appt.status != AppointmentStatus.REGISTERED:
        raise ConflictError(f"Cannot edit an appointment in status '{appt.status.value}'.", error_code="illegal_edit")

    updates = data.model_dump(exclude_unset=True, exclude_none=True)
    before = {"visit_type": appt.visit_type, "doctor_id": str(appt.doctor_id)}

    if "visit_type" in updates and updates["visit_type"] != appt.visit_type:
        new_batch = await resolve_batch(session, scheduled_at=appt.scheduled_at, visit_type=updates["visit_type"])
        await _enforce_batch_capacity(session, new_batch, scheduled_at=appt.scheduled_at, exclude_appointment_id=appt.id)
        appt.batch_id = new_batch.id if new_batch else None

    for field, value in updates.items():
        setattr(appt, field, value)

    await session.flush()
    await session.refresh(appt)

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="appointment.edited", entity_type="Appointment", entity_id=str(appt.id),
        before_state=before, after_state={"visit_type": appt.visit_type, "doctor_id": str(appt.doctor_id)},
    )
    return appt


async def reschedule_appointment(
    session: AsyncSession, appointment_id: uuid.UUID, *, new_scheduled_at: datetime, reason: str,
    actor_id: uuid.UUID, actor_role: str,
) -> Appointment:
    """Moves an appointment to a new date/time, re-resolving its batch for
    the new slot, and appends an AppointmentHistory row preserving the old
    date/time rather than overwriting it. Only appointments still at
    REGISTERED can be rescheduled — once a patient has arrived or the
    visit has otherwise progressed, moving the clock back doesn't make
    sense and should go through cancel + rebook instead."""
    appt = await get_appointment(session, appointment_id)

    if appt.status != AppointmentStatus.REGISTERED:
        raise ConflictError(
            f"Cannot reschedule an appointment in status '{appt.status.value}'.",
            error_code="illegal_reschedule",
        )

    old_scheduled_at = appt.scheduled_at
    now = datetime.now(timezone.utc)
    new_batch = await resolve_batch(session, scheduled_at=new_scheduled_at, visit_type=appt.visit_type)
    await _enforce_batch_capacity(session, new_batch, scheduled_at=new_scheduled_at, exclude_appointment_id=appt.id)

    session.add(AppointmentHistory(
        appointment_id=appt.id, old_scheduled_at=old_scheduled_at, new_scheduled_at=new_scheduled_at,
        reason=reason, changed_by_id=actor_id, changed_at=now,
    ))

    appt.scheduled_at = new_scheduled_at
    appt.batch_id = new_batch.id if new_batch else None
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="appointment.rescheduled", entity_type="Appointment", entity_id=str(appt.id),
        before_state={"scheduled_at": old_scheduled_at.isoformat()},
        after_state={"scheduled_at": new_scheduled_at.isoformat()}, reason=reason,
    )

    return appt


async def list_appointment_history(session: AsyncSession, appointment_id: uuid.UUID) -> list[AppointmentHistory]:
    result = await session.execute(
        select(AppointmentHistory)
        .where(AppointmentHistory.appointment_id == appointment_id)
        .order_by(AppointmentHistory.changed_at.desc())
    )
    return list(result.scalars().all())


async def list_batches(session: AsyncSession, *, active_only: bool = True) -> list[AppointmentBatch]:
    stmt = select(AppointmentBatch).order_by(AppointmentBatch.display_order)
    if active_only:
        stmt = stmt.where(AppointmentBatch.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def get_batch(session: AsyncSession, batch_id: uuid.UUID) -> AppointmentBatch:
    batch = await session.get(AppointmentBatch, batch_id)
    if not batch:
        raise NotFoundError("Appointment batch not found", error_code="batch_not_found")
    return batch


async def create_batch(session: AsyncSession, data, *, actor_id: uuid.UUID, actor_role: str) -> AppointmentBatch:
    batch = AppointmentBatch(
        name=data.name, start_time=data.start_time, end_time=data.end_time,
        visit_types=",".join(data.visit_types), display_order=data.display_order, capacity=data.capacity,
    )
    session.add(batch)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="appointment_batch.created", entity_type="AppointmentBatch", entity_id=str(batch.id),
        after_state={"name": batch.name},
    )
    return batch


async def update_batch(session: AsyncSession, batch_id: uuid.UUID, data, *, actor_id: uuid.UUID, actor_role: str) -> AppointmentBatch:
    batch = await get_batch(session, batch_id)
    updates = data.model_dump(exclude_unset=True)
    if "visit_types" in updates:
        updates["visit_types"] = ",".join(updates["visit_types"])
    for field, value in updates.items():
        setattr(batch, field, value)
    await session.flush()
    await session.refresh(batch)
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="appointment_batch.updated", entity_type="AppointmentBatch", entity_id=str(batch.id),
    )
    return batch


async def list_today_grouped_by_batch(
    session: AsyncSession, *, day: date, doctor_id: uuid.UUID | None = None
) -> list[tuple[AppointmentBatch | None, list[Appointment], int, int | None]]:
    """The front-desk dashboard's core view — today's appointments grouped
    into their configured batches, in batch display order, with any
    appointment whose slot/visit_type doesn't match a configured batch
    collected into a trailing "Unbatched" (None) group rather than being
    dropped. Each group also reports its booked count and remaining
    capacity (None = unlimited) for the reschedule-slot-picker UX."""
    appointments = await list_appointments_for_day(session, day=day, doctor_id=doctor_id)
    batches = await list_batches(session)

    by_batch: dict[uuid.UUID | None, list[Appointment]] = {b.id: [] for b in batches}
    by_batch[None] = []
    for appt in appointments:
        by_batch.setdefault(appt.batch_id, []).append(appt)

    def booked_and_remaining(batch: AppointmentBatch | None, appts: list[Appointment]) -> tuple[int, int | None]:
        booked = sum(1 for a in appts if a.status not in _INACTIVE_STATUSES)
        remaining = (batch.capacity - booked) if (batch and batch.capacity is not None) else None
        return booked, remaining

    groups: list[tuple[AppointmentBatch | None, list[Appointment], int, int | None]] = []
    for b in batches:
        booked, remaining = booked_and_remaining(b, by_batch[b.id])
        groups.append((b, by_batch[b.id], booked, remaining))
    if by_batch[None]:
        booked, remaining = booked_and_remaining(None, by_batch[None])
        groups.append((None, by_batch[None], booked, remaining))
    return groups


async def list_future_appointments(
    session: AsyncSession, params: AppointmentListParams, *, limit: int = 200
) -> list[Appointment]:
    """Server-side filtered upcoming-appointments list (spec: never load
    the whole table and filter in the browser). Defaults to "from today
    onward" when no from_date is given."""
    today_local = datetime.now(HOSPITAL_TIMEZONE).date()
    from_day = params.from_date or today_local
    start_utc, _ = _local_day_bounds_utc(from_day)
    stmt = select(Appointment).where(Appointment.scheduled_at >= start_utc)

    if params.to_date:
        _, end_utc = _local_day_bounds_utc(params.to_date)
        stmt = stmt.where(Appointment.scheduled_at < end_utc)
    if params.doctor_id:
        stmt = stmt.where(Appointment.doctor_id == params.doctor_id)
    if params.status:
        stmt = stmt.where(Appointment.status == params.status)
    else:
        stmt = stmt.where(Appointment.status.notin_(_INACTIVE_STATUSES + (AppointmentStatus.COMPLETED,)))
    if params.channel:
        stmt = stmt.where(Appointment.channel == params.channel)
    if params.q:
        stmt = stmt.join(Patient, Patient.id == Appointment.patient_id).where(Patient.full_name.ilike(f"%{params.q}%"))

    result = await session.execute(stmt.order_by(Appointment.scheduled_at).limit(limit))
    return list(result.scalars().all())


async def list_appointments_by_channel(
    session: AsyncSession, params: AppointmentListParams, *, limit: int = 200
) -> list[Appointment]:
    """Unrestricted-by-date list filtered by channel — backs the Phone
    Call Appointment history table, which needs to show every phone
    booking regardless of whether it's past or future, unlike the
    future/closed lists which are each scoped to one side of "today"."""
    stmt = select(Appointment)
    if params.channel:
        stmt = stmt.where(Appointment.channel == params.channel)
    if params.from_date:
        start_utc, _ = _local_day_bounds_utc(params.from_date)
        stmt = stmt.where(Appointment.scheduled_at >= start_utc)
    if params.to_date:
        _, end_utc = _local_day_bounds_utc(params.to_date)
        stmt = stmt.where(Appointment.scheduled_at < end_utc)
    if params.doctor_id:
        stmt = stmt.where(Appointment.doctor_id == params.doctor_id)
    if params.status:
        stmt = stmt.where(Appointment.status == params.status)
    if params.q:
        stmt = stmt.join(Patient, Patient.id == Appointment.patient_id).where(Patient.full_name.ilike(f"%{params.q}%"))

    result = await session.execute(stmt.order_by(Appointment.scheduled_at.desc()).limit(limit))
    return list(result.scalars().all())


async def list_closed_appointments(
    session: AsyncSession, params: AppointmentListParams, *, limit: int = 200
) -> list[Appointment]:
    """Completed/cancelled/no-show appointments — retrievable indefinitely,
    never hard-deleted, with the same server-side date/doctor/status
    filters as the future list."""
    closed_statuses = (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW)
    stmt = select(Appointment).where(Appointment.status.in_(closed_statuses))

    if params.from_date:
        start_utc, _ = _local_day_bounds_utc(params.from_date)
        stmt = stmt.where(Appointment.scheduled_at >= start_utc)
    if params.to_date:
        _, end_utc = _local_day_bounds_utc(params.to_date)
        stmt = stmt.where(Appointment.scheduled_at < end_utc)
    if params.doctor_id:
        stmt = stmt.where(Appointment.doctor_id == params.doctor_id)
    if params.status:
        stmt = stmt.where(Appointment.status == params.status)
    if params.q:
        stmt = stmt.join(Patient, Patient.id == Appointment.patient_id).where(Patient.full_name.ilike(f"%{params.q}%"))

    result = await session.execute(stmt.order_by(Appointment.scheduled_at.desc()).limit(limit))
    return list(result.scalars().all())

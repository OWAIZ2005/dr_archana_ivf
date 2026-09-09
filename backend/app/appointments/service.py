import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.appointments.models import ALLOWED_TRANSITIONS, Appointment, AppointmentStatus
from app.appointments.schemas import AppointmentCreate
from app.audit.service import record_audit_event
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.events.bus import EventType, emit


async def create_appointment(session: AsyncSession, data: AppointmentCreate) -> Appointment:
    appt = Appointment(**data.model_dump())
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
    stmt = select(Appointment).where(
        Appointment.scheduled_at >= datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
        Appointment.scheduled_at < datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc),
    )
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

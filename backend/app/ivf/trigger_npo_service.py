"""Trigger-injection and NPO logic, plus the two scheduled-task bodies that
generate their hospital-staff notifications.

Notifications go through app.messaging.service (provider abstraction, MessageLog)
— this module never talks to a provider directly and never messages a patient.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.ivf.models import IVFCycle, NpoWindow, TriggerInjection, TriggerStatus
from app.ivf.trigger_npo_schemas import NpoCreate, TriggerCreate, TriggerReschedule
from app.messaging import service as messaging_service
from app.patients.models import Couple, Patient
from app.users.models import User

# Placeholder — a single-tenant deployment. Move to config if the product ever
# serves more than one clinic. Used only in notification wording.
CLINIC_DISPLAY_NAME = "Dr. Archana IVF & Women Centre"

TRIGGER_EVENT = "trigger_due"
NPO_EVENT = "npo_started"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Context builders (patient name / doctor / date / time for the templates)
# --------------------------------------------------------------------------- #

async def _cycle_people(session: AsyncSession, cycle: IVFCycle) -> tuple[Patient | None, User | None]:
    couple = await session.get(Couple, cycle.couple_id)
    patient: Patient | None = None
    if couple is not None:
        patient = await session.get(Patient, couple.female_patient_id)
    doctor = await session.get(User, cycle.primary_doctor_id)
    return patient, doctor


def _when_tokens(when: datetime) -> dict[str, str]:
    return {"date": when.strftime("%d %b %Y"), "time": when.strftime("%I:%M %p")}


# --------------------------------------------------------------------------- #
# Trigger injection
# --------------------------------------------------------------------------- #

async def _get_cycle(session: AsyncSession, cycle_id: uuid.UUID) -> IVFCycle:
    cycle = await session.get(IVFCycle, cycle_id)
    if cycle is None:
        raise NotFoundError("IVF cycle not found")
    return cycle


async def create_trigger(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    data: TriggerCreate,
    *,
    actor_id: uuid.UUID,
    actor_role: str,
) -> TriggerInjection:
    await _get_cycle(session, cycle_id)
    existing = (
        await session.execute(
            sa.select(TriggerInjection).where(TriggerInjection.cycle_id == cycle_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("This cycle already has a trigger injection record.")

    trigger = TriggerInjection(
        cycle_id=cycle_id,
        medicine=data.medicine,
        planned_at=data.planned_at,
        status=TriggerStatus.planned,
    )
    session.add(trigger)
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="ivf.trigger_created", entity_type="TriggerInjection", entity_id=str(trigger.id),
        after_state={"medicine": trigger.medicine, "planned_at": trigger.planned_at.isoformat()},
    )
    return trigger


async def get_trigger(session: AsyncSession, trigger_id: uuid.UUID) -> TriggerInjection:
    trigger = await session.get(TriggerInjection, trigger_id)
    if trigger is None:
        raise NotFoundError("Trigger injection not found")
    return trigger


async def get_trigger_for_cycle(session: AsyncSession, cycle_id: uuid.UUID) -> TriggerInjection | None:
    return (
        await session.execute(
            sa.select(TriggerInjection).where(TriggerInjection.cycle_id == cycle_id)
        )
    ).scalar_one_or_none()


async def reschedule_trigger(
    session: AsyncSession,
    trigger_id: uuid.UUID,
    data: TriggerReschedule,
    *,
    actor_id: uuid.UUID,
    actor_role: str,
) -> TriggerInjection:
    trigger = await get_trigger(session, trigger_id)
    if trigger.confirmed_at is not None:
        raise ValidationFailedError("A confirmed trigger cannot be rescheduled.")

    previous = trigger.planned_at
    if data.planned_at == previous:
        return trigger

    trigger.planned_at = data.planned_at
    # Restart the reminder run against the NEW time: no reminder already sent
    # counts, and a previously-overdue trigger is planned again.
    trigger.reminders_sent = 0
    trigger.last_reminder_at = None
    trigger.acknowledged_at = None
    trigger.acknowledged_by_id = None
    if trigger.status is TriggerStatus.overdue:
        trigger.status = TriggerStatus.planned
    await session.flush()

    # Previous value is preserved in the audit trail (before/after), per §4.
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="ivf.trigger_rescheduled", entity_type="TriggerInjection", entity_id=str(trigger.id),
        before_state={"planned_at": previous.isoformat()},
        after_state={"planned_at": data.planned_at.isoformat()},
    )
    return trigger


async def acknowledge_trigger(
    session: AsyncSession, trigger_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str
) -> TriggerInjection:
    trigger = await get_trigger(session, trigger_id)
    if trigger.confirmed_at is not None:
        return trigger  # already past acknowledgement
    if trigger.acknowledged_at is None:
        trigger.acknowledged_at = _utcnow()
        trigger.acknowledged_by_id = actor_id
        await session.flush()
        await record_audit_event(
            session, actor_id=actor_id, actor_role=actor_role,
            action="ivf.trigger_acknowledged", entity_type="TriggerInjection", entity_id=str(trigger.id),
            after_state={"acknowledged_at": trigger.acknowledged_at.isoformat()},
        )
    return trigger


async def confirm_trigger(
    session: AsyncSession,
    trigger_id: uuid.UUID,
    confirmed_at: datetime | None,
    *,
    actor_id: uuid.UUID,
    actor_role: str,
) -> TriggerInjection:
    trigger = await get_trigger(session, trigger_id)
    if trigger.confirmed_at is not None:
        return trigger

    now = _utcnow()
    trigger.confirmed_at = confirmed_at or now
    trigger.confirmed_by_id = actor_id
    trigger.status = TriggerStatus.confirmed
    if trigger.acknowledged_at is None:  # confirmation implies acknowledgement
        trigger.acknowledged_at = now
        trigger.acknowledged_by_id = actor_id
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="ivf.trigger_confirmed", entity_type="TriggerInjection", entity_id=str(trigger.id),
        after_state={"confirmed_at": trigger.confirmed_at.isoformat()},
    )
    return trigger


# --------------------------------------------------------------------------- #
# NPO
# --------------------------------------------------------------------------- #

async def create_npo(
    session: AsyncSession,
    cycle_id: uuid.UUID,
    data: NpoCreate,
    *,
    actor_id: uuid.UUID,
    actor_role: str,
) -> NpoWindow:
    await _get_cycle(session, cycle_id)

    start_at = data.start_at
    if start_at is None:
        # procedure_at is guaranteed present by the schema validator.
        lead = get_settings().NPO_LEAD_TIME_MINUTES
        start_at = data.procedure_at - timedelta(minutes=lead)  # type: ignore[operator]

    window = NpoWindow(cycle_id=cycle_id, start_at=start_at, reason=data.reason)
    session.add(window)
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="ivf.npo_created", entity_type="NpoWindow", entity_id=str(window.id),
        after_state={"start_at": window.start_at.isoformat(), "reason": window.reason},
    )
    return window


async def get_npo(session: AsyncSession, npo_id: uuid.UUID) -> NpoWindow:
    window = await session.get(NpoWindow, npo_id)
    if window is None:
        raise NotFoundError("NPO window not found")
    return window


async def get_npo_for_cycle(session: AsyncSession, cycle_id: uuid.UUID) -> NpoWindow | None:
    return (
        await session.execute(
            sa.select(NpoWindow).where(NpoWindow.cycle_id == cycle_id).order_by(NpoWindow.created_at.desc())
        )
    ).scalars().first()


# --------------------------------------------------------------------------- #
# Scheduled-task bodies (idempotent; `now` is injectable for tests)
# --------------------------------------------------------------------------- #

async def process_trigger_reminders(
    session: AsyncSession, *, now: datetime | None = None
) -> dict[str, int]:
    """Send the trigger reminder(s) due as of ``now`` for every open trigger,
    and mark a trigger OVERDUE once the last reminder has gone out unacknowledged.

    Attempt N is due at ``planned_at + (N-1) * interval``. Safe to run every
    minute and safe to run twice concurrently — the send is deduped on
    ``(trigger_due, trigger_id, attempt)``.
    """
    now = now or _utcnow()
    s = get_settings()
    interval = timedelta(minutes=s.TRIGGER_REMINDER_INTERVAL_MINUTES)
    max_attempts = s.TRIGGER_REMINDER_MAX_ATTEMPTS

    open_triggers = (
        await session.execute(
            sa.select(TriggerInjection).where(
                TriggerInjection.status == TriggerStatus.planned,
                TriggerInjection.acknowledged_at.is_(None),
                TriggerInjection.confirmed_at.is_(None),
                TriggerInjection.planned_at <= now,
            )
        )
    ).scalars().all()

    sent = 0
    overdue = 0
    for trigger in open_triggers:
        # How many attempts should have fired by `now`.
        elapsed = now - trigger.planned_at
        due_attempt = 1 + math.floor(elapsed / interval)
        due_attempt = max(1, min(due_attempt, max_attempts))

        cycle = await session.get(IVFCycle, trigger.cycle_id)
        patient, _doctor = await _cycle_people(session, cycle) if cycle else (None, None)
        ctx = {
            "name": patient.full_name if patient else "the patient",
            "clinic": CLINIC_DISPLAY_NAME,
            **_when_tokens(trigger.planned_at),
        }

        # Include the planned time in the idempotency key so a reschedule
        # (which resets reminders_sent) legitimately starts a fresh run at
        # attempt 1 without colliding with the previous run's key.
        run = int(trigger.planned_at.timestamp())
        while trigger.reminders_sent < due_attempt:
            attempt = trigger.reminders_sent + 1
            await messaging_service.send_event_notification(
                session,
                template_name="trigger_due",
                context=ctx,
                event_type=TRIGGER_EVENT,
                event_id=str(trigger.id),
                attempt=attempt,
                dedupe_key=f"{TRIGGER_EVENT}:{trigger.id}:{run}:{attempt}",
                patient_id=patient.id if patient else None,
                to_phone=None,  # internal staff notification
            )
            trigger.reminders_sent = attempt
            trigger.last_reminder_at = now
            sent += 1

        if trigger.reminders_sent >= max_attempts:
            trigger.status = TriggerStatus.overdue
            overdue += 1

    await session.flush()
    return {"reminders_sent": sent, "marked_overdue": overdue}


async def process_npo_notifications(
    session: AsyncSession, *, now: datetime | None = None
) -> dict[str, int]:
    """Generate the one-shot 'NPO started' staff notification for every NPO
    window whose start time has passed and that has not been notified yet."""
    now = now or _utcnow()
    windows = (
        await session.execute(
            sa.select(NpoWindow).where(
                NpoWindow.notified_at.is_(None),
                NpoWindow.start_at <= now,
            )
        )
    ).scalars().all()

    sent = 0
    for window in windows:
        cycle = await session.get(IVFCycle, window.cycle_id)
        patient, _doctor = await _cycle_people(session, cycle) if cycle else (None, None)
        ctx = {
            "name": patient.full_name if patient else "the patient",
            "clinic": CLINIC_DISPLAY_NAME,
            "reason": window.reason,
            **_when_tokens(window.start_at),
        }
        await messaging_service.send_event_notification(
            session,
            template_name="npo_started",
            context=ctx,
            event_type=NPO_EVENT,
            event_id=str(window.id),
            attempt=1,
            patient_id=patient.id if patient else None,
            to_phone=None,  # internal staff notification
        )
        window.notified_at = now
        sent += 1

    await session.flush()
    return {"npo_notifications_sent": sent}

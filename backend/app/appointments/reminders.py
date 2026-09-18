"""Front-desk follow-up reminders — a lightweight, standalone task list
against a patient (optionally tied to an appointment). Lives inside the
appointments package (not a new top-level module) since it's tightly
coupled to the same Patient/Appointment/User entities and doesn't
warrant its own package, but is exposed at its own top-level `/reminders`
prefix to match the resource, not the package layout.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.appointments.models import Reminder, ReminderStatus
from app.appointments.schemas import ReminderCreate, ReminderOut, ReminderUpdate
from app.audit.service import record_audit_event
from app.core.database import get_db
from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.users.models import User

router = APIRouter(prefix="/reminders", tags=["reminders"])


async def list_reminders(
    session: AsyncSession, *, status: ReminderStatus | None = None, patient_id: uuid.UUID | None = None,
    due_before: datetime | None = None, limit: int = 200,
) -> list[Reminder]:
    stmt = select(Reminder)
    if status:
        stmt = stmt.where(Reminder.status == status)
    if patient_id:
        stmt = stmt.where(Reminder.patient_id == patient_id)
    if due_before:
        stmt = stmt.where(Reminder.due_at <= due_before)
    result = await session.execute(stmt.order_by(Reminder.due_at).limit(limit))
    return list(result.scalars().all())


async def get_reminder(session: AsyncSession, reminder_id: uuid.UUID) -> Reminder:
    reminder = await session.get(Reminder, reminder_id)
    if not reminder:
        raise NotFoundError("Reminder not found", error_code="reminder_not_found")
    return reminder


async def create_reminder(session: AsyncSession, data: ReminderCreate, *, actor_id: uuid.UUID, actor_role: str) -> Reminder:
    reminder = Reminder(**data.model_dump(), created_by_id=actor_id)
    session.add(reminder)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="reminder.created", entity_type="Reminder", entity_id=str(reminder.id),
        after_state={"reason": reminder.reason, "due_at": reminder.due_at.isoformat()},
    )
    return reminder


async def update_reminder(
    session: AsyncSession, reminder_id: uuid.UUID, data: ReminderUpdate, *, actor_id: uuid.UUID, actor_role: str
) -> Reminder:
    reminder = await get_reminder(session, reminder_id)
    if reminder.status != ReminderStatus.PENDING:
        raise ConflictError(f"Cannot edit a reminder that is already '{reminder.status.value}'.", error_code="reminder_not_pending")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(reminder, field, value)
    await session.flush()
    await session.refresh(reminder)
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="reminder.updated", entity_type="Reminder", entity_id=str(reminder.id),
    )
    return reminder


async def _set_reminder_status(
    session: AsyncSession, reminder_id: uuid.UUID, new_status: ReminderStatus, *, actor_id: uuid.UUID, actor_role: str
) -> Reminder:
    reminder = await get_reminder(session, reminder_id)
    if reminder.status != ReminderStatus.PENDING:
        raise ConflictError(f"Reminder is already '{reminder.status.value}'.", error_code="reminder_not_pending")
    now = datetime.now(timezone.utc)
    reminder.status = new_status
    reminder.completed_by_id = actor_id
    reminder.completed_at = now
    await session.flush()
    await session.refresh(reminder)
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action=f"reminder.{new_status.value}", entity_type="Reminder", entity_id=str(reminder.id),
    )
    return reminder


async def complete_reminder(session: AsyncSession, reminder_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str) -> Reminder:
    return await _set_reminder_status(session, reminder_id, ReminderStatus.COMPLETED, actor_id=actor_id, actor_role=actor_role)


async def cancel_reminder(session: AsyncSession, reminder_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str) -> Reminder:
    return await _set_reminder_status(session, reminder_id, ReminderStatus.CANCELLED, actor_id=actor_id, actor_role=actor_role)


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #

@router.get("", response_model=list[ReminderOut])
async def list_reminders_endpoint(
    status: ReminderStatus | None = Query(default=None),
    patient_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("reminders.manage")),
) -> list[ReminderOut]:
    return await list_reminders(session, status=status, patient_id=patient_id)


@router.get("/{reminder_id}", response_model=ReminderOut)
async def get_reminder_endpoint(
    reminder_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("reminders.manage")),
) -> ReminderOut:
    return await get_reminder(session, reminder_id)


@router.post("", response_model=ReminderOut, status_code=201)
async def create_reminder_endpoint(
    body: ReminderCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("reminders.manage")),
) -> ReminderOut:
    return await create_reminder(session, body, actor_id=current.id, actor_role=current.role.code)


@router.patch("/{reminder_id}", response_model=ReminderOut)
async def update_reminder_endpoint(
    reminder_id: str,
    body: ReminderUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("reminders.manage")),
) -> ReminderOut:
    return await update_reminder(session, reminder_id, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/{reminder_id}/complete", response_model=ReminderOut)
async def complete_reminder_endpoint(
    reminder_id: str,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("reminders.manage")),
) -> ReminderOut:
    return await complete_reminder(session, reminder_id, actor_id=current.id, actor_role=current.role.code)


@router.post("/{reminder_id}/cancel", response_model=ReminderOut)
async def cancel_reminder_endpoint(
    reminder_id: str,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("reminders.manage")),
) -> ReminderOut:
    return await cancel_reminder(session, reminder_id, actor_id=current.id, actor_role=current.role.code)

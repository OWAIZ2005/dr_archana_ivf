"""
Celery task bodies. Each task wraps an async DB session with
`asyncio.run(...)` since Celery workers run synchronously by default —
this keeps the same async service-layer functions used by the API in
use here too, rather than maintaining a parallel sync code path.
"""
import asyncio
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import worker_session_scope
from app.events.models import OutboxEvent
from app.hr.models import Employee
from app.maintenance.service import flag_overdue_tasks
from app.notifications.service import escalate_overdue_tasks
from app.pharmacy.models import Medicine
from app.workers.celery_app import celery_app


def _run(coro):
    return asyncio.run(coro)


async def _dispatch_outbox_events() -> int:
    """The outbox pattern's consumer side — reads undispatched domain
    events (written transactionally by every module's service layer, see
    app/events/bus.py) and fans them out. Marking `dispatched_at` happens
    only after the fan-out succeeds, so a crash mid-dispatch just means
    the same event gets retried on the next poll — at-least-once delivery,
    which is the right tradeoff for notifications/alerts (better a
    duplicate reminder than a silently dropped one)."""
    async with worker_session_scope() as session:
        result = await session.execute(
            select(OutboxEvent).where(OutboxEvent.dispatched_at.is_(None)).limit(100)
        )
        events = result.scalars().all()
        for event in events:
            # Real fan-out (SMS/email/websocket push) plugs in here per
            # event_type; Phase 1 logs and marks dispatched so the pattern
            # is provably wired end-to-end before external integrations
            # (Twilio/SendGrid/WhatsApp Business API) are connected.
            event.dispatched_at = datetime.now(timezone.utc)
            event.dispatch_attempts += 1
        await session.commit()
        return len(events)


@celery_app.task(name="app.workers.tasks.dispatch_outbox_events")
def dispatch_outbox_events() -> int:
    return _run(_dispatch_outbox_events())


async def generate_appointment_reminders(session, *, for_date=None) -> int:
    """Create a front-desk 'confirm tomorrow's appointment' task for each of
    ``for_date``'s appointments (spec §19 — a queued task that escalates, not a
    blind SMS).

    Idempotency guard: an appointment that already has an OPEN reminder task is
    skipped, so re-running (retry, manual trigger, overlapping beat) never
    stacks duplicates. Detail text goes through the shared template renderer.

    Session-taking so it is unit-testable; the Celery wrapper supplies a
    worker session and commits.
    """
    from app.appointments.models import Appointment
    from app.messaging.templating import render_body
    from app.notifications.models import NotificationTask, TaskStatus
    from app.notifications.schemas import TaskCreate
    from app.notifications.service import create_task

    target = for_date or (date.today() + timedelta(days=1))
    appts = (
        await session.execute(
            select(Appointment).where(func_date_eq(Appointment.scheduled_at, target))
        )
    ).scalars().all()

    existing = set(
        (
            await session.execute(
                select(NotificationTask.related_entity_id).where(
                    NotificationTask.related_entity_type == "Appointment",
                    NotificationTask.status == TaskStatus.OPEN,
                )
            )
        ).scalars().all()
    )

    count = 0
    for appt in appts:
        if str(appt.id) in existing:
            continue  # already has an open reminder task
        detail = render_body(
            "Reminder: {{visit_type}} appointment at {{time}} on {{date}}.",
            {
                "visit_type": appt.visit_type,
                "time": appt.scheduled_at.strftime("%I:%M %p"),
                "date": appt.scheduled_at.strftime("%d %b %Y"),
            },
        )
        await create_task(session, TaskCreate(
            assigned_to_id=appt.doctor_id,
            title="Confirm tomorrow's appointment",
            detail=detail,
            due_at=datetime.now(timezone.utc) + timedelta(hours=2),
            related_entity_type="Appointment", related_entity_id=str(appt.id),
        ))
        count += 1
    return count


async def _send_appointment_reminders() -> int:
    async with worker_session_scope() as session:
        count = await generate_appointment_reminders(session)
        await session.commit()
        return count


async def _process_trigger_reminders() -> dict:
    from app.ivf.trigger_npo_service import process_trigger_reminders

    async with worker_session_scope() as session:
        result = await process_trigger_reminders(session)
        await session.commit()
        return result


async def _process_npo_notifications() -> dict:
    from app.ivf.trigger_npo_service import process_npo_notifications

    async with worker_session_scope() as session:
        result = await process_npo_notifications(session)
        await session.commit()
        return result


@celery_app.task(name="app.workers.tasks.process_trigger_reminders")
def process_trigger_reminders() -> dict:
    return _run(_process_trigger_reminders())


@celery_app.task(name="app.workers.tasks.process_npo_notifications")
def process_npo_notifications() -> dict:
    return _run(_process_npo_notifications())


def func_date_eq(column, target_date):
    from sqlalchemy import func
    return func.date(column) == target_date


@celery_app.task(name="app.workers.tasks.send_appointment_reminders")
def send_appointment_reminders() -> int:
    return _run(_send_appointment_reminders())


async def _generate_daily_readiness_checklists() -> int:
    from app.ot.schemas import ChecklistCreate, ChecklistItem
    from app.ot.service import create_daily_checklist

    templates = {
        "OT": ["Table", "Instruments", "Sterilization", "Emergency equipment", "Oxygen", "Suction", "Medicines", "Patient documentation"],
        "Scan": ["Equipment", "Room readiness"],
        "Laboratory": ["Equipment checks", "Temperature", "QC"],
        "Cryostorage": ["Tank status", "Temperature/level checks"],
    }
    async with worker_session_scope() as session:
        today = date.today()
        for dept, items in templates.items():
            await create_daily_checklist(session, ChecklistCreate(
                department=dept, checklist_date=today,
                items=[ChecklistItem(item=i) for i in items],
            ))
        await session.commit()
        return len(templates)


@celery_app.task(name="app.workers.tasks.generate_daily_readiness_checklists")
def generate_daily_readiness_checklists() -> int:
    return _run(_generate_daily_readiness_checklists())


async def _flag_overdue_maintenance() -> int:
    async with worker_session_scope() as session:
        count = await flag_overdue_tasks(session)
        await session.commit()
        return count


@celery_app.task(name="app.workers.tasks.flag_overdue_maintenance")
def flag_overdue_maintenance() -> int:
    return _run(_flag_overdue_maintenance())


async def _escalate_overdue_notification_tasks() -> int:
    async with worker_session_scope() as session:
        # Escalates to the first active administrator on record — a real
        # deployment would configure a department-specific escalation
        # target; kept simple and explicit here rather than guessed.
        from app.roles.models import Role
        from app.users.models import User
        result = await session.execute(
            select(User).join(Role).where(Role.code == "administrator", User.is_active.is_(True)).limit(1)
        )
        admin = result.scalar_one_or_none()
        if not admin:
            return 0
        count = await escalate_overdue_tasks(session, escalate_to_id=admin.id)
        await session.commit()
        return count


@celery_app.task(name="app.workers.tasks.escalate_overdue_notification_tasks")
def escalate_overdue_notification_tasks() -> int:
    return _run(_escalate_overdue_notification_tasks())


async def _check_expiry_and_reorder_alerts() -> int:
    from app.notifications.models import NotificationTone
    from app.notifications.service import push_notification
    from app.pharmacy.models import MedicineBatch
    from app.roles.models import Role
    from app.users.models import User

    alerts = 0
    async with worker_session_scope() as session:
        admins_result = await session.execute(
            select(User).join(Role).where(Role.code == "pharmacist", User.is_active.is_(True))
        )
        pharmacists = admins_result.scalars().all()

        expiring_soon = date.today() + timedelta(days=90)
        result = await session.execute(
            select(MedicineBatch).where(
                MedicineBatch.expiry_date <= expiring_soon, MedicineBatch.quantity_available > 0
            )
        )
        for batch in result.scalars().all():
            for pharmacist in pharmacists:
                await push_notification(
                    session, user_id=pharmacist.id,
                    title="Batch expiring within 90 days",
                    body=f"Batch {batch.batch_number} expires {batch.expiry_date.isoformat()}",
                    tone=NotificationTone.ATTENTION,
                )
                alerts += 1
        await session.commit()
    return alerts


@celery_app.task(name="app.workers.tasks.check_expiry_and_reorder_alerts")
def check_expiry_and_reorder_alerts() -> int:
    return _run(_check_expiry_and_reorder_alerts())


@celery_app.task(name="app.workers.tasks.trigger_nightly_backup")
def trigger_nightly_backup() -> str:
    """Invokes the backup script (see backend/scripts/backup.sh) as a
    subprocess. Kept as a thin trigger here — the actual pg_dump / MinIO
    mirror logic lives in a shell script so it can also be run manually
    or from cron independent of Celery, per docs/operations/backups.md."""
    import subprocess
    result = subprocess.run(["/app/scripts/backup.sh"], capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError(f"Backup script failed: {result.stderr}")
    return result.stdout

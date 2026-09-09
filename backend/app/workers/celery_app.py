"""
Celery application — background processing for everything that must
never block a user-facing request, per spec §4 ("Never make a user
wait for a background operation that does not need to complete
synchronously"): reminders, reorder alerts, daily checklist generation,
report/PDF generation, notification delivery, backups.
"""
from celery import Celery
from celery.schedules import crontab

from app.core import all_models  # noqa: F401  (registers every model on Base.metadata —
# task bodies build ORM objects with cross-module FKs, e.g. ReadinessChecklist -> User,
# and unlike app.main (which imports every router and thus every model transitively),
# this process only imports app.workers.tasks, so without this nothing else guarantees
# the referenced tables exist on Base.metadata before a task's first flush)
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "archana_hmis",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    # app.reports.job_tasks holds the asynchronous report-generation task; it
    # reuses this same broker/result backend and adds no new Redis settings.
    include=["app.workers.tasks", "app.reports.job_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # fair dispatch — no single worker hoards a burst of tasks
    task_acks_late=True,  # a crashed worker doesn't silently drop a task
    # Eager mode: `.delay()` / `.apply_async()` run the task inline and
    # synchronously. Off in every real run; the report-job unit tests set
    # CELERY_TASK_ALWAYS_EAGER=1 so they can drive enqueue -> generate ->
    # status without a running broker or worker.
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=settings.CELERY_TASK_ALWAYS_EAGER,
)

celery_app.conf.beat_schedule = {
    "dispatch-outbox-events": {
        "task": "app.workers.tasks.dispatch_outbox_events",
        "schedule": 10.0,  # every 10s — the outbox pattern's polling side
    },
    "appointment-reminders": {
        "task": "app.workers.tasks.send_appointment_reminders",
        "schedule": crontab(hour=17, minute=0),  # 5 PM daily, per spec §19's example
    },
    "trigger-injection-reminders": {
        "task": "app.workers.tasks.process_trigger_reminders",
        "schedule": 60.0,  # every minute — drives the T, T+5, T+10 staff reminders
    },
    "npo-window-notifications": {
        "task": "app.workers.tasks.process_npo_notifications",
        "schedule": 60.0,  # every minute — fires the one-shot "NPO started" notice
    },
    "generate-daily-checklists": {
        "task": "app.workers.tasks.generate_daily_readiness_checklists",
        "schedule": crontab(hour=6, minute=0),  # before the clinic opens
    },
    "flag-overdue-maintenance": {
        "task": "app.workers.tasks.flag_overdue_maintenance",
        "schedule": crontab(hour=7, minute=0),
    },
    "escalate-overdue-tasks": {
        "task": "app.workers.tasks.escalate_overdue_notification_tasks",
        "schedule": crontab(minute="*/30"),
    },
    "expiry-and-reorder-alerts": {
        "task": "app.workers.tasks.check_expiry_and_reorder_alerts",
        "schedule": crontab(hour=8, minute=0),
    },
    "nightly-backup": {
        "task": "app.workers.tasks.trigger_nightly_backup",
        "schedule": crontab(hour=2, minute=0),  # 2 AM — see docs/operations/backups.md
    },
}

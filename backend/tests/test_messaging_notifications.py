"""Hospital notification system: template rendering, trigger-injection and NPO
workflows, the T / T+5 / T+10 reminder schedule, idempotency, and the
ConsoleProvider demo behaviour.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.ivf.models import IVFCycle, NpoWindow, TriggerInjection, TriggerStatus
from app.ivf.trigger_npo_schemas import NpoCreate, TriggerCreate, TriggerReschedule
from app.ivf import trigger_npo_service as tn
from app.messaging.models import MessageLog, MessageStatus
from app.messaging.providers import CONSOLE_PROVIDER_TAG
from app.messaging.seed import seed_message_templates
from app.messaging.templating import render_body


# --------------------------------------------------------------------------- #
# 1. Template rendering
# --------------------------------------------------------------------------- #

class TestRenderBody:
    def test_replaces_every_supported_token(self):
        body = "Hi {{name}}, {{doctor}} sees you at {{clinic}} on {{date}} at {{time}}."
        out = render_body(body, {
            "name": "Priya", "doctor": "Dr. Archana", "clinic": "DAIVF",
            "date": "05 Sep 2026", "time": "10:00 PM",
        })
        assert out == "Hi Priya, Dr. Archana sees you at DAIVF on 05 Sep 2026 at 10:00 PM."

    def test_unknown_tokens_are_left_unchanged(self):
        out = render_body("Hi {{name}}, ref {{unknown_token}} stays.", {"name": "Priya"})
        assert out == "Hi Priya, ref {{unknown_token}} stays."

    def test_missing_known_token_is_left_unchanged(self):
        # 'time' is supported but not supplied -> not blanked, still visible
        out = render_body("At {{time}}", {})
        assert out == "At {{time}}"

    def test_none_value_renders_empty(self):
        assert render_body("x{{a}}y", {"a": None}) == "xy"

    def test_whitespace_inside_braces_ok(self):
        assert render_body("{{ name }}", {"name": "P"}) == "P"


# --------------------------------------------------------------------------- #
# Fixtures: templates + one cycle with a patient and a doctor
# --------------------------------------------------------------------------- #

@pytest_asyncio.fixture
async def templates(db_session):
    await seed_message_templates(db_session)
    await db_session.commit()


@pytest_asyncio.fixture
async def cycle(db_session, doctor_user):
    from app.patients.models import Couple, Patient

    female = Patient(uhid=f"T-{uuid4().hex[:8]}", full_name="Priya Raman", gender="female")
    male = Patient(uhid=f"T-{uuid4().hex[:8]}", full_name="Arjun Kumar", gender="male")
    db_session.add_all([female, male])
    await db_session.flush()
    couple = Couple(female_patient_id=female.id, male_patient_id=male.id)
    db_session.add(couple)
    await db_session.flush()
    c = IVFCycle(
        cycle_number=f"IVF-{uuid4().hex[:8]}", couple_id=couple.id,
        primary_doctor_id=doctor_user.id, protocol="GnRH Antagonist Protocol",
        treatment="IVF with ICSI", started_at=datetime.now(timezone.utc).date(),
    )
    db_session.add(c)
    await db_session.commit()
    c._female_patient = female  # convenience for assertions
    return c


async def _make_trigger(db_session, cycle, doctor_user, *, planned_at) -> TriggerInjection:
    return await tn.create_trigger(
        db_session, cycle.id, TriggerCreate(medicine="Inj. Ovitrelle 250mcg", planned_at=planned_at),
        actor_id=doctor_user.id, actor_role="doctor",
    )


def _trigger_logs(session_result):
    return [r for r in session_result if r.event_type == "trigger_due"]


# --------------------------------------------------------------------------- #
# 2-4. Trigger CRUD + reschedule + confirm
# --------------------------------------------------------------------------- #

class TestTriggerCrud:
    async def test_create_and_get(self, db_session, cycle, doctor_user):
        planned = datetime.now(timezone.utc) + timedelta(hours=2)
        t = await _make_trigger(db_session, cycle, doctor_user, planned_at=planned)
        assert t.status is TriggerStatus.planned
        assert t.reminders_sent == 0
        got = await tn.get_trigger(db_session, t.id)
        assert got.id == t.id

    async def test_one_per_cycle(self, db_session, cycle, doctor_user):
        planned = datetime.now(timezone.utc) + timedelta(hours=2)
        await _make_trigger(db_session, cycle, doctor_user, planned_at=planned)
        from app.core.exceptions import ConflictError
        with pytest.raises(ConflictError):
            await _make_trigger(db_session, cycle, doctor_user, planned_at=planned)

    async def test_reschedule_uses_new_time_and_resets_run(self, db_session, cycle, doctor_user):
        old = datetime(2026, 9, 5, 22, 0, tzinfo=timezone.utc)   # 10:00 PM
        new = datetime(2026, 9, 5, 22, 30, tzinfo=timezone.utc)  # 10:30 PM
        t = await _make_trigger(db_session, cycle, doctor_user, planned_at=old)
        t.reminders_sent = 2  # pretend some reminders already fired
        await db_session.flush()

        t = await tn.reschedule_trigger(
            db_session, t.id, TriggerReschedule(planned_at=new), actor_id=doctor_user.id, actor_role="doctor"
        )
        assert t.planned_at == new
        assert t.reminders_sent == 0  # run restarted against the new time

        # audit trail keeps the previous value
        from app.audit.models import AuditEvent
        ev = (await db_session.execute(
            select(AuditEvent).where(AuditEvent.action == "ivf.trigger_rescheduled")
        )).scalars().all()
        assert ev and ev[-1].before_state["planned_at"].startswith("2026-09-05T22:00")

    async def test_confirm_sets_state(self, db_session, cycle, doctor_user):
        t = await _make_trigger(
            db_session, cycle, doctor_user, planned_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        t = await tn.confirm_trigger(db_session, t.id, None, actor_id=doctor_user.id, actor_role="doctor")
        assert t.status is TriggerStatus.confirmed
        assert t.confirmed_at is not None and t.confirmed_by_id == doctor_user.id
        assert t.acknowledged_at is not None  # confirmation implies acknowledgement

    async def test_confirmed_trigger_cannot_be_rescheduled(self, db_session, cycle, doctor_user):
        t = await _make_trigger(
            db_session, cycle, doctor_user, planned_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        await tn.confirm_trigger(db_session, t.id, None, actor_id=doctor_user.id, actor_role="doctor")
        from app.core.exceptions import ValidationFailedError
        with pytest.raises(ValidationFailedError):
            await tn.reschedule_trigger(
                db_session, t.id, TriggerReschedule(planned_at=datetime.now(timezone.utc)),
                actor_id=doctor_user.id, actor_role="doctor",
            )


# --------------------------------------------------------------------------- #
# 5. Trigger reminder schedule: T, T+5, T+10, no fourth, overdue, ack stops
# --------------------------------------------------------------------------- #

class TestTriggerReminderSchedule:
    async def _logs(self, db_session, trigger_id):
        rows = (await db_session.execute(
            select(MessageLog).where(
                MessageLog.event_type == "trigger_due", MessageLog.event_id == str(trigger_id)
            ).order_by(MessageLog.attempt)
        )).scalars().all()
        return rows

    async def test_full_unacknowledged_sequence(self, db_session, cycle, doctor_user, templates):
        T = datetime(2026, 9, 5, 22, 0, tzinfo=timezone.utc)
        t = await _make_trigger(db_session, cycle, doctor_user, planned_at=T)

        # Before T: nothing
        await tn.process_trigger_reminders(db_session, now=T - timedelta(minutes=1))
        assert await self._logs(db_session, t.id) == []

        # At T: first reminder
        await tn.process_trigger_reminders(db_session, now=T)
        rows = await self._logs(db_session, t.id)
        assert [r.attempt for r in rows] == [1]
        assert rows[0].sent_by_id is None  # system-triggered
        assert rows[0].patient_id == cycle._female_patient.id
        assert "Priya Raman" in rows[0].body and "10:00 PM" in rows[0].body

        # T+5: second
        await tn.process_trigger_reminders(db_session, now=T + timedelta(minutes=5))
        assert [r.attempt for r in await self._logs(db_session, t.id)] == [1, 2]

        # T+10: third, and now OVERDUE
        await tn.process_trigger_reminders(db_session, now=T + timedelta(minutes=10))
        rows = await self._logs(db_session, t.id)
        assert [r.attempt for r in rows] == [1, 2, 3]
        t = await tn.get_trigger(db_session, t.id)
        assert t.status is TriggerStatus.overdue

        # T+15: NO fourth reminder
        await tn.process_trigger_reminders(db_session, now=T + timedelta(minutes=15))
        assert [r.attempt for r in await self._logs(db_session, t.id)] == [1, 2, 3]

    async def test_acknowledge_stops_further_reminders(self, db_session, cycle, doctor_user, templates):
        T = datetime(2026, 9, 5, 22, 0, tzinfo=timezone.utc)
        t = await _make_trigger(db_session, cycle, doctor_user, planned_at=T)

        await tn.process_trigger_reminders(db_session, now=T)  # attempt 1
        await tn.acknowledge_trigger(db_session, t.id, actor_id=doctor_user.id, actor_role="doctor")

        await tn.process_trigger_reminders(db_session, now=T + timedelta(minutes=5))
        await tn.process_trigger_reminders(db_session, now=T + timedelta(minutes=10))
        assert [r.attempt for r in await self._logs(db_session, t.id)] == [1]
        t = await tn.get_trigger(db_session, t.id)
        assert t.status is TriggerStatus.planned  # acknowledged, never went overdue

    async def test_confirm_before_next_reminder_stops_it(self, db_session, cycle, doctor_user, templates):
        T = datetime(2026, 9, 5, 22, 0, tzinfo=timezone.utc)
        t = await _make_trigger(db_session, cycle, doctor_user, planned_at=T)
        await tn.process_trigger_reminders(db_session, now=T)
        await tn.confirm_trigger(db_session, t.id, None, actor_id=doctor_user.id, actor_role="doctor")
        await tn.process_trigger_reminders(db_session, now=T + timedelta(minutes=20))
        assert [r.attempt for r in await self._logs(db_session, t.id)] == [1]

    async def test_reschedule_moves_the_schedule(self, db_session, cycle, doctor_user, templates):
        T = datetime(2026, 9, 5, 22, 0, tzinfo=timezone.utc)
        t = await _make_trigger(db_session, cycle, doctor_user, planned_at=T)
        await tn.process_trigger_reminders(db_session, now=T)  # attempt 1 at old time
        assert len(await self._logs(db_session, t.id)) == 1

        new_T = T + timedelta(minutes=30)
        await tn.reschedule_trigger(
            db_session, t.id, TriggerReschedule(planned_at=new_T), actor_id=doctor_user.id, actor_role="doctor"
        )
        # Old-time tick no longer produces anything; the run was reset.
        await tn.process_trigger_reminders(db_session, now=T + timedelta(minutes=10))
        assert len(await self._logs(db_session, t.id)) == 1
        # At the NEW time, the sequence starts again as attempt 1.
        await tn.process_trigger_reminders(db_session, now=new_T)
        rows = await self._logs(db_session, t.id)
        assert [r.attempt for r in rows][-1] == 1 and len(rows) == 2

    async def test_duplicate_run_does_not_duplicate_notifications(self, db_session, cycle, doctor_user, templates):
        T = datetime(2026, 9, 5, 22, 0, tzinfo=timezone.utc)
        t = await _make_trigger(db_session, cycle, doctor_user, planned_at=T)
        # Same tick processed twice (retry / overlapping beat)
        await tn.process_trigger_reminders(db_session, now=T)
        await tn.process_trigger_reminders(db_session, now=T)
        rows = await self._logs(db_session, t.id)
        assert [r.attempt for r in rows] == [1]

    async def test_console_provider_records_demo_tag(self, db_session, cycle, doctor_user, templates):
        T = datetime(2026, 9, 5, 22, 0, tzinfo=timezone.utc)
        t = await _make_trigger(db_session, cycle, doctor_user, planned_at=T)
        await tn.process_trigger_reminders(db_session, now=T)
        row = (await self._logs(db_session, t.id))[0]
        assert row.provider == "console"
        assert row.provider_message_id == CONSOLE_PROVIDER_TAG
        assert row.status is MessageStatus.SENT


# --------------------------------------------------------------------------- #
# 7-8. NPO
# --------------------------------------------------------------------------- #

class TestNpo:
    async def test_create_with_explicit_start(self, db_session, cycle, doctor_user):
        start = datetime(2026, 9, 6, 6, 0, tzinfo=timezone.utc)
        w = await tn.create_npo(
            db_session, cycle.id, NpoCreate(reason="Oocyte retrieval", start_at=start),
            actor_id=doctor_user.id, actor_role="doctor",
        )
        assert w.start_at == start and w.notified_at is None

    async def test_create_from_procedure_time_uses_configured_lead(self, db_session, cycle, doctor_user):
        from app.core.config import get_settings
        lead = get_settings().NPO_LEAD_TIME_MINUTES
        proc = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
        w = await tn.create_npo(
            db_session, cycle.id, NpoCreate(reason="Retrieval", procedure_at=proc),
            actor_id=doctor_user.id, actor_role="doctor",
        )
        assert w.start_at == proc - timedelta(minutes=lead)

    async def test_notification_generated_once_when_window_starts(self, db_session, cycle, doctor_user, templates):
        start = datetime(2026, 9, 6, 6, 0, tzinfo=timezone.utc)
        w = await tn.create_npo(
            db_session, cycle.id, NpoCreate(reason="Oocyte retrieval under sedation", start_at=start),
            actor_id=doctor_user.id, actor_role="doctor",
        )
        # before start -> nothing
        await tn.process_npo_notifications(db_session, now=start - timedelta(minutes=1))
        rows = (await db_session.execute(
            select(MessageLog).where(MessageLog.event_type == "npo_started", MessageLog.event_id == str(w.id))
        )).scalars().all()
        assert rows == []

        # at start -> one notification, includes name / time / reason
        await tn.process_npo_notifications(db_session, now=start)
        await tn.process_npo_notifications(db_session, now=start + timedelta(minutes=5))  # idempotent re-run
        rows = (await db_session.execute(
            select(MessageLog).where(MessageLog.event_type == "npo_started", MessageLog.event_id == str(w.id))
        )).scalars().all()
        assert len(rows) == 1
        body = rows[0].body
        assert "Priya Raman" in body and "06:00 AM" in body and "sedation" in body
        assert rows[0].sent_by_id is None and rows[0].provider == "console"
        w = await tn.get_npo(db_session, w.id)
        assert w.notified_at is not None


# --------------------------------------------------------------------------- #
# 9. Appointment reminder idempotency (existing task, now guarded)
# --------------------------------------------------------------------------- #

class TestAppointmentReminderIdempotency:
    async def test_rerun_does_not_stack_tasks(self, db_session, doctor_user):
        from datetime import date
        from app.appointments.models import Appointment, AppointmentChannel, AppointmentStatus
        from app.notifications.models import NotificationTask
        from app.workers.tasks import generate_appointment_reminders

        tomorrow = date.today() + timedelta(days=1)
        appt = Appointment(
            patient_id=(await _a_patient(db_session)).id,
            doctor_id=doctor_user.id,
            visit_type="Follow-up",
            channel=AppointmentChannel.__members__[next(iter(AppointmentChannel.__members__))],
            status=AppointmentStatus.__members__[next(iter(AppointmentStatus.__members__))],
            scheduled_at=datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=10),
        )
        db_session.add(appt)
        await db_session.flush()

        n1 = await generate_appointment_reminders(db_session, for_date=tomorrow)
        n2 = await generate_appointment_reminders(db_session, for_date=tomorrow)  # no-op for this appt
        assert n1 == 1 and n2 == 0

        tasks = (await db_session.execute(
            select(NotificationTask).where(
                NotificationTask.related_entity_type == "Appointment",
                NotificationTask.related_entity_id == str(appt.id),
            )
        )).scalars().all()
        assert len(tasks) == 1
        assert "Follow-up" in tasks[0].detail  # rendered via the shared template renderer


async def _a_patient(db_session):
    from app.patients.models import Patient
    p = Patient(uhid=f"AP-{uuid4().hex[:8]}", full_name="Appt Patient", gender="female")
    db_session.add(p)
    await db_session.flush()
    return p

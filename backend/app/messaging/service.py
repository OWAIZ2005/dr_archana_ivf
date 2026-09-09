import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.messaging.models import (
    MessageCategory,
    MessageChannel,
    MessageLog,
    MessageStatus,
    MessageTemplate,
    PatientCommsPreference,
)
from app.messaging.providers import get_provider
from app.messaging.schemas import CommsPreferenceUpdate, MessageTemplateCreate, SendMessageRequest
from app.messaging.templating import render_body
from app.patients.models import Patient


async def create_template(session: AsyncSession, data: MessageTemplateCreate) -> MessageTemplate:
    template = MessageTemplate(**data.model_dump())
    session.add(template)
    await session.flush()
    return template


async def list_templates(session: AsyncSession) -> list[MessageTemplate]:
    result = await session.execute(select(MessageTemplate).where(MessageTemplate.is_active.is_(True)))
    return list(result.scalars().all())


async def get_template_by_name(session: AsyncSession, name: str) -> MessageTemplate | None:
    return (
        await session.execute(select(MessageTemplate).where(MessageTemplate.name == name))
    ).scalar_one_or_none()


async def get_comms_preference(session: AsyncSession, patient_id: uuid.UUID) -> PatientCommsPreference:
    result = await session.execute(select(PatientCommsPreference).where(PatientCommsPreference.patient_id == patient_id))
    pref = result.scalar_one_or_none()
    if not pref:
        # Default is opt-out, per source doc §27's "consent/opt-in handling
        # where required" — a patient with no recorded preference has not
        # consented to promotional messaging.
        pref = PatientCommsPreference(patient_id=patient_id, promotional_opt_in=False)
        session.add(pref)
        await session.flush()
    return pref


async def update_comms_preference(
    session: AsyncSession, patient_id: uuid.UUID, data: CommsPreferenceUpdate, *, actor_id: uuid.UUID, actor_role: str
) -> PatientCommsPreference:
    pref = await get_comms_preference(session, patient_id)
    before = pref.promotional_opt_in
    pref.promotional_opt_in = data.promotional_opt_in
    pref.updated_by_id = actor_id
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="messaging.comms_preference_updated", entity_type="PatientCommsPreference", entity_id=str(patient_id),
        before_state={"promotional_opt_in": before}, after_state={"promotional_opt_in": data.promotional_opt_in},
    )
    return pref


# --------------------------------------------------------------------------- #
# Core delivery — every path (manual send, appointment reminder, trigger/NPO
# notification) funnels through _deliver, which is the ONLY caller of the
# provider. Providers are swapped via settings.MESSAGE_PROVIDER; nothing here
# or upstream is provider-specific.
# --------------------------------------------------------------------------- #

async def _deliver(
    session: AsyncSession,
    *,
    body: str,
    channel: MessageChannel,
    category: MessageCategory,
    to_phone: str | None,
    patient_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
    sent_by_id: uuid.UUID | None = None,
    event_type: str = "manual",
    event_id: str | None = None,
    attempt: int = 1,
    dedupe_key: str | None = None,
) -> MessageLog | None:
    """Persist a MessageLog and hand the body to the configured provider.

    If ``dedupe_key`` is given and a row already has it, this is a no-op and
    returns ``None`` — that is what makes retried / overlapping scheduled sends
    idempotent (no duplicate log row, no duplicate provider call).
    """
    provider = get_provider()

    values: dict[str, Any] = dict(
        patient_id=patient_id,
        template_id=template_id,
        channel=channel,
        category=category,
        body=body,
        status=MessageStatus.QUEUED,
        sent_by_id=sent_by_id,
        provider=provider.name,
        event_type=event_type,
        event_id=event_id,
        attempt=attempt,
        dedupe_key=dedupe_key,
    )

    if dedupe_key is not None:
        stmt = (
            pg_insert(MessageLog)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["dedupe_key"])
            .returning(MessageLog.id)
        )
        new_id = (await session.execute(stmt)).scalar_one_or_none()
        if new_id is None:
            return None  # already sent for this (event, attempt) — idempotent skip
        log = await session.get(MessageLog, new_id)
        assert log is not None
    else:
        log = MessageLog(**values)
        session.add(log)
        await session.flush()

    success, provider_message_id, failure_reason = await provider.send(
        to_phone=to_phone, body=body, channel=channel
    )
    log.status = MessageStatus.SENT if success else MessageStatus.FAILED
    log.provider_message_id = provider_message_id
    log.failure_reason = failure_reason
    if success:
        log.sent_at = datetime.now(timezone.utc)
    await session.flush()
    return log


async def send_event_notification(
    session: AsyncSession,
    *,
    template_name: str,
    context: dict[str, Any],
    event_type: str,
    event_id: str,
    attempt: int = 1,
    dedupe_key: str | None = None,
    patient_id: uuid.UUID | None = None,
    to_phone: str | None = None,
    channel: MessageChannel | None = None,
) -> MessageLog | None:
    """Render ``template_name`` with ``context`` and deliver it as a
    system-triggered (``sent_by_id`` NULL) transactional message, idempotent on
    ``dedupe_key`` (defaults to ``f"{event_type}:{event_id}:{attempt}"``; callers
    whose "attempt 1" can legitimately recur — e.g. after a trigger reschedule —
    pass an explicit key that includes a run discriminator).

    Used by the trigger / NPO / appointment-reminder scheduled tasks. For
    trigger and NPO these are INTERNAL staff notifications: ``to_phone`` is
    left ``None`` and the console provider just logs them.
    """
    template = await get_template_by_name(session, template_name)
    if template is None:
        raise NotFoundError(f"Message template '{template_name}' is not seeded.")

    return await _deliver(
        session,
        body=render_body(template.body, context),
        channel=channel or template.channel,
        category=MessageCategory.TRANSACTIONAL,  # never gated on opt-in
        to_phone=to_phone,
        patient_id=patient_id,
        template_id=template.id,
        sent_by_id=None,
        event_type=event_type,
        event_id=event_id,
        attempt=attempt,
        dedupe_key=dedupe_key or f"{event_type}:{event_id}:{attempt}",
    )


async def send_message(
    session: AsyncSession, data: SendMessageRequest, *, actor_id: uuid.UUID | None, actor_role: str | None
) -> MessageLog:
    """Manual, staff-initiated patient message. Transactional messages always
    send; promotional messages are blocked unless the patient has opted in
    (source doc §27), enforced here so no caller can bypass the check."""
    patient = await session.get(Patient, data.patient_id)
    if not patient or not patient.phone:
        raise NotFoundError("Patient not found or has no phone number on file")

    body = data.body
    if data.template_id:
        template = await session.get(MessageTemplate, data.template_id)
        if not template:
            raise NotFoundError("Message template not found")
        body = render_body(template.body, {"name": patient.full_name})
    if not body:
        raise ValidationFailedError("A message needs either a template_id or an explicit body.")

    if data.category == MessageCategory.PROMOTIONAL:
        pref = await get_comms_preference(session, data.patient_id)
        if not pref.promotional_opt_in:
            raise ValidationFailedError(
                "This patient has not opted in to promotional messages.",
                error_code="promotional_opt_out",
            )

    log = await _deliver(
        session,
        body=body,
        channel=data.channel,
        category=data.category,
        to_phone=patient.phone,
        patient_id=data.patient_id,
        template_id=data.template_id,
        sent_by_id=actor_id,
        event_type="manual",
    )
    assert log is not None  # no dedupe_key -> always created

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role or "system",
        action="messaging.message_sent" if log.status is MessageStatus.SENT else "messaging.message_failed",
        entity_type="MessageLog", entity_id=str(log.id),
        after_state={"channel": data.channel.value, "category": data.category.value, "status": log.status.value},
    )
    return log


async def list_message_history(session: AsyncSession, patient_id: uuid.UUID) -> list[MessageLog]:
    result = await session.execute(
        select(MessageLog).where(MessageLog.patient_id == patient_id).order_by(MessageLog.created_at.desc())
    )
    return list(result.scalars().all())


async def list_event_messages(
    session: AsyncSession, *, event_type: str, event_id: str
) -> list[MessageLog]:
    """Notification history for one trigger / NPO event, oldest first."""
    result = await session.execute(
        select(MessageLog)
        .where(MessageLog.event_type == event_type, MessageLog.event_id == event_id)
        .order_by(MessageLog.created_at)
    )
    return list(result.scalars().all())

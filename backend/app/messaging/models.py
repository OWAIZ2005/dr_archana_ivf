"""
WhatsApp/SMS messaging — new requirement (source doc §26-27). NEEDS
HOSPITAL/CLIENT CONFIRMATION (NEW_FEATURES_GAP_ANALYSIS.md §22): the
actual provider (WhatsApp Business API requires a Meta Business
verification process with real calendar time — worth starting that
conversation in parallel with any development, not after). Nothing here
assumes a specific provider; `app/messaging/providers.py` defines the
interface every provider plugs into, and the only implementation
shipped is a safe no-op that logs instead of sending, so this module is
usable (queued, logged, auditable) before a provider is ever chosen and
swapping one in later touches provider code only, not this schema or any
caller.

Transactional and promotional messages are modeled as one table with a
`category` split, per the source doc's own instruction to "keep
promotional messaging separate from critical clinical notifications" —
kept separate by category/consent enforcement (a promotional send checks
opt-in, a transactional one does not), not by being two different
half-duplicated tables.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class MessageChannel(str, enum.Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"


class MessageCategory(str, enum.Enum):
    TRANSACTIONAL = "transactional"  # appointment reminders, treatment alerts — never gated on opt-in
    PROMOTIONAL = "promotional"  # packages/offers — gated on PatientCommsPreference.promotional_opt_in


class MessageStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class MessageTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "message_templates"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    channel: Mapped[MessageChannel] = mapped_column(Enum(MessageChannel), nullable=False)
    category: Mapped[MessageCategory] = mapped_column(Enum(MessageCategory), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. "Hi {{name}}, your appointment is on {{date}}."
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PatientCommsPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One row per patient — the opt-in record source doc §27 requires
    ('Consent/opt-in handling where required'). Transactional messages
    are never gated on this; only MessageCategory.PROMOTIONAL sends check it."""
    __tablename__ = "patient_comms_preferences"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), unique=True, nullable=False, index=True)
    promotional_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class MessageLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "message_logs"

    # Nullable: internal hospital notifications (trigger/NPO) are addressed to
    # staff, not a patient. Patient-facing sends and, for context, trigger/NPO
    # sends still record the cycle's patient here so a per-patient history works.
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True, index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("message_templates.id"), nullable=True)
    channel: Mapped[MessageChannel] = mapped_column(Enum(MessageChannel), nullable=False)
    category: Mapped[MessageCategory] = mapped_column(Enum(MessageCategory), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # the rendered message actually sent, kept even if the template changes later
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), default=MessageStatus.QUEUED, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # null for system-triggered sends (e.g. reminders)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Which MessageProvider produced this row ("console" for the demo no-op,
    # "msg91" once wired). Makes it explicit in history/exports that a
    # "console" row was never actually delivered anywhere.
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Links a log row back to the domain event that caused it, and the retry
    # attempt number (1 for one-shot sends; 1..N for trigger reminders). The
    # frontend shows attempt count from this.
    event_type: Mapped[str | None] = mapped_column(String(48), nullable=True)  # trigger_due | npo_started | appointment_reminder | report_ready | manual
    event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Deterministic per (event, attempt) key, e.g. "trigger_due:<id>:1". A
    # UNIQUE constraint makes every scheduled send idempotent: a retried or
    # overlapping Celery run that tries to insert the same key hits the
    # constraint and is skipped, so no duplicate MessageLog / no duplicate send.
    dedupe_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)

    __table_args__ = (
        Index("ix_message_logs_event", "event_type", "event_id"),
    )

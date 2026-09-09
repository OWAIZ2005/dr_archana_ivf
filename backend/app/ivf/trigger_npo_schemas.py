"""Request/response shapes for trigger-injection and NPO endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.ivf.models import TriggerStatus


# --------------------------- Trigger injection ---------------------------- #

class TriggerCreate(BaseModel):
    medicine: str
    planned_at: datetime


class TriggerReschedule(BaseModel):
    planned_at: datetime


class TriggerConfirm(BaseModel):
    # Optional override; defaults to "now" server-side.
    confirmed_at: datetime | None = None


class TriggerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cycle_id: uuid.UUID
    medicine: str
    planned_at: datetime
    status: TriggerStatus
    acknowledged_at: datetime | None
    acknowledged_by_id: uuid.UUID | None
    confirmed_at: datetime | None
    confirmed_by_id: uuid.UUID | None
    reminders_sent: int
    last_reminder_at: datetime | None
    created_at: datetime


# --------------------------------- NPO ----------------------------------- #

class NpoCreate(BaseModel):
    """Provide ``start_at`` directly, OR ``procedure_at`` to have the server
    compute start_at = procedure_at - settings.NPO_LEAD_TIME_MINUTES."""
    reason: str
    start_at: datetime | None = None
    procedure_at: datetime | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "NpoCreate":
        if self.start_at is None and self.procedure_at is None:
            raise ValueError("Provide either start_at or procedure_at.")
        return self


class NpoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cycle_id: uuid.UUID
    start_at: datetime
    reason: str
    notified_at: datetime | None
    created_at: datetime


# ----------------------- Notification history --------------------------- #

class EventMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str | None
    event_id: str | None
    attempt: int
    body: str
    channel: str
    status: str
    provider: str | None
    provider_message_id: str | None
    sent_at: datetime | None
    created_at: datetime

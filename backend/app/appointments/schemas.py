import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.appointments.models import (
    COMMUNICATION_OUTCOMES,
    AppointmentChannel,
    AppointmentStatus,
    CommunicationChannel,
    ReminderStatus,
)


class AppointmentCreate(BaseModel):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    scheduled_at: datetime
    visit_type: str
    channel: AppointmentChannel
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus
    reason: str | None = None  # required by the service layer for CANCELLED/NO_SHOW


class AppointmentReschedule(BaseModel):
    new_scheduled_at: datetime
    reason: str = Field(min_length=1, max_length=500)


class AppointmentEdit(BaseModel):
    """Corrects a booking mistake (wrong visit type/doctor picked) without
    touching the date/time — that's what reschedule is for. Editing the
    visit_type re-resolves the batch for the appointment's existing
    scheduled_at, since the same time can land in a different batch (or
    no batch) depending on the type."""
    visit_type: str | None = None
    doctor_id: uuid.UUID | None = None
    notes: str | None = None


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    scheduled_at: datetime
    visit_type: str
    channel: AppointmentChannel
    status: AppointmentStatus
    checked_in_at: datetime | None
    cancellation_reason: str | None
    marked_not_arrived_at: datetime | None
    notes: str | None
    token_number: int | None
    batch_id: uuid.UUID | None


class AppointmentHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    appointment_id: uuid.UUID
    old_scheduled_at: datetime
    new_scheduled_at: datetime
    reason: str | None
    changed_by_id: uuid.UUID
    changed_at: datetime


class AppointmentBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    start_time: time
    end_time: time
    visit_types: list[str]
    display_order: int
    is_active: bool
    capacity: int | None

    @classmethod
    def from_model(cls, batch) -> "AppointmentBatchOut":
        return cls(
            id=batch.id, name=batch.name, start_time=batch.start_time, end_time=batch.end_time,
            visit_types=[v.strip() for v in batch.visit_types.split(",") if v.strip()],
            display_order=batch.display_order, is_active=batch.is_active, capacity=batch.capacity,
        )


class AppointmentBatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    start_time: time
    end_time: time
    visit_types: list[str] = Field(min_length=1)
    display_order: int = 0
    capacity: int | None = Field(default=None, gt=0)

    @field_validator("end_time")
    @classmethod
    def _end_after_start(cls, v: time, info) -> time:
        start = info.data.get("start_time")
        if start is not None and v <= start:
            raise ValueError("end_time must be after start_time")
        return v


class AppointmentBatchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    start_time: time | None = None
    end_time: time | None = None
    visit_types: list[str] | None = None
    display_order: int | None = None
    is_active: bool | None = None
    capacity: int | None = None


class BatchGroupOut(BaseModel):
    batch: AppointmentBatchOut | None  # None = the "Unbatched" bucket
    appointments: list[AppointmentOut]
    booked_count: int
    remaining: int | None  # None = unlimited (no capacity configured)


# --------------------------------------------------------------------------- #
# Future / closed appointment lists
# --------------------------------------------------------------------------- #

class AppointmentListParams(BaseModel):
    """Shared server-side filter shape for the future/closed/by-channel
    appointment lists — never load the full table into the browser and
    filter in JS."""
    from_date: date | None = None
    to_date: date | None = None
    doctor_id: uuid.UUID | None = None
    status: AppointmentStatus | None = None
    channel: AppointmentChannel | None = None
    q: str | None = None


# --------------------------------------------------------------------------- #
# Reminders
# --------------------------------------------------------------------------- #

class ReminderCreate(BaseModel):
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    reason: str = Field(min_length=1, max_length=255)
    due_at: datetime
    notes: str | None = Field(default=None, max_length=2000)


class ReminderUpdate(BaseModel):
    reason: str | None = Field(default=None, min_length=1, max_length=255)
    due_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None
    reason: str
    due_at: datetime
    status: ReminderStatus
    notes: str | None
    created_by_id: uuid.UUID
    completed_by_id: uuid.UUID | None
    completed_at: datetime | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Patient communications (contact log)
# --------------------------------------------------------------------------- #

class CommunicationCreate(BaseModel):
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    channel: CommunicationChannel
    outcome: str
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("outcome")
    @classmethod
    def _valid_outcome(cls, v: str) -> str:
        if v not in COMMUNICATION_OUTCOMES:
            raise ValueError(f"outcome must be one of {COMMUNICATION_OUTCOMES}")
        return v


class CommunicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None
    channel: CommunicationChannel
    outcome: str
    notes: str | None
    contacted_by_id: uuid.UUID
    contacted_at: datetime

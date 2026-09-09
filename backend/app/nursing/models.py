"""
Nursing records — a minimal, hospital-unconfirmed scaffold for recording
patient vitals/observations during a visit.

Deliberately tiny: only blood pressure (systolic/diastolic), temperature, and
free-text notes, because the full nursing workflow has NOT been confirmed by
the hospital yet. Do not add pulse / SpO2 / weight / medication administration /
IV fluids / IVF-specific nursing fields here without a confirmed requirement.

Follows the existing clinical-record shape (see app/clinical/models.py
``Consultation``): the record belongs to an individual ``Patient`` (never the
couple), optionally links to the ``Appointment`` it was taken during, records
the acting user by id, and carries the same ``corrects_*`` columns so a
future correction endpoint is a pure addition — no name or patient data is
copied into the row.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class NursingRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "nursing_records"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    # The visit this was recorded during, when there is one. Nullable, mirroring
    # Consultation.appointment_id — a nurse may record vitals outside a booked
    # appointment.
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True, index=True
    )
    # The nurse / staff member who recorded it — set from the authenticated
    # user, never entered by hand.
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    blood_pressure_systolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blood_pressure_diastolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Unit (deg F / deg C) is NOT decided here — the hospital has not confirmed
    # it. Stored as a plain number; the UI currently labels it "degF".
    temperature: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Correction linkage, identical to app/clinical/models.py::Consultation. No
    # endpoint writes these yet (v1 is create + read only, records are
    # immutable); the columns exist so a confirmed correction workflow can be
    # added later without a data migration.
    corrects_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nursing_records.id"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Read-time only — the display name is resolved through the FK, never stored
    # on the row.
    recorded_by = relationship("User", lazy="selectin")

    @property
    def recorded_by_name(self) -> str | None:
        return self.recorded_by.full_name if self.recorded_by else None

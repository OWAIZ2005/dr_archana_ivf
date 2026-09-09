import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NursingRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None = None

    # Basic, non-clinical validation only: numeric-and-non-negative when
    # provided. No "normal range" checks — those are a hospital policy that has
    # not been given.
    blood_pressure_systolic: int | None = Field(default=None, ge=0)
    blood_pressure_diastolic: int | None = Field(default=None, ge=0)
    temperature: float | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def _at_least_one_value(self) -> "NursingRecordCreate":
        if (
            self.blood_pressure_systolic is None
            and self.blood_pressure_diastolic is None
            and self.temperature is None
            and not (self.notes or "").strip()
        ):
            raise ValueError("Record at least one of blood pressure, temperature or notes.")
        return self


class NursingRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None
    recorded_by_id: uuid.UUID
    recorded_by_name: str | None
    blood_pressure_systolic: int | None
    blood_pressure_diastolic: int | None
    temperature: float | None
    notes: str | None
    recorded_at: datetime
    created_at: datetime

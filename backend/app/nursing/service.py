import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.appointments.models import Appointment
from app.audit.service import record_audit_event
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.nursing.models import NursingRecord
from app.nursing.schemas import NursingRecordCreate
from app.patients.models import Patient


async def create_nursing_record(
    session: AsyncSession, data: NursingRecordCreate, *, actor_id: uuid.UUID, actor_role: str
) -> NursingRecord:
    patient = await session.get(Patient, data.patient_id)
    if patient is None:
        raise NotFoundError("Patient not found", error_code="patient_not_found")

    if data.appointment_id is not None:
        appt = await session.get(Appointment, data.appointment_id)
        if appt is None:
            raise NotFoundError("Appointment not found", error_code="appointment_not_found")
        if appt.patient_id != data.patient_id:
            raise ValidationFailedError(
                "That appointment belongs to a different patient.",
                error_code="appointment_patient_mismatch",
            )

    record = NursingRecord(
        patient_id=data.patient_id,
        appointment_id=data.appointment_id,
        recorded_by_id=actor_id,
        blood_pressure_systolic=data.blood_pressure_systolic,
        blood_pressure_diastolic=data.blood_pressure_diastolic,
        temperature=data.temperature,
        notes=(data.notes or None),
        recorded_at=datetime.now(timezone.utc),
    )
    session.add(record)
    await session.flush()
    # Load the recorded_by relationship so NursingRecordOut.recorded_by_name
    # serialises without a lazy load on the async session.
    await session.refresh(record, attribute_names=["recorded_by"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="nursing.record_created", entity_type="NursingRecord", entity_id=str(record.id),
        after_state={
            "patient_id": str(data.patient_id),
            "appointment_id": str(data.appointment_id) if data.appointment_id else None,
            "has_bp": data.blood_pressure_systolic is not None or data.blood_pressure_diastolic is not None,
            "has_temperature": data.temperature is not None,
        },
    )
    return record


async def list_nursing_records_for_patient(
    session: AsyncSession, patient_id: uuid.UUID
) -> list[NursingRecord]:
    result = await session.execute(
        select(NursingRecord)
        .where(NursingRecord.patient_id == patient_id)
        .order_by(NursingRecord.recorded_at.desc(), NursingRecord.id.desc())
    )
    return list(result.scalars().all())


async def list_nursing_records_for_appointment(
    session: AsyncSession, appointment_id: uuid.UUID
) -> list[NursingRecord]:
    result = await session.execute(
        select(NursingRecord)
        .where(NursingRecord.appointment_id == appointment_id)
        .order_by(NursingRecord.recorded_at.desc(), NursingRecord.id.desc())
    )
    return list(result.scalars().all())

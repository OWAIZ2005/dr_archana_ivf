import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.core.exceptions import NotFoundError
from app.patients.models import Patient
from app.prescription.models import Prescription, PrescriptionLine
from app.prescription.pdf import render_prescription_pdf
from app.prescription.schemas import PrescriptionCreate
from app.users.models import User


async def create_prescription(
    session: AsyncSession, data: PrescriptionCreate, *, actor_id: uuid.UUID, actor_role: str
) -> Prescription:
    prescription = Prescription(
        patient_id=data.patient_id, cycle_id=data.cycle_id, prescribed_by_id=actor_id,
        category=data.category, notes=data.notes,
    )
    session.add(prescription)
    await session.flush()

    for line in data.lines:
        session.add(PrescriptionLine(prescription_id=prescription.id, **line.model_dump()))
    await session.flush()
    await session.refresh(prescription, attribute_names=["lines"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="prescription.created", entity_type="Prescription", entity_id=str(prescription.id),
        after_state={"line_count": len(data.lines), "category": data.category},
    )
    return prescription


async def get_prescription(session: AsyncSession, prescription_id: uuid.UUID) -> Prescription:
    prescription = await session.get(Prescription, prescription_id)
    if not prescription:
        raise NotFoundError("Prescription not found")
    return prescription


async def list_prescriptions_for_patient(session: AsyncSession, patient_id: uuid.UUID) -> list[Prescription]:
    result = await session.execute(
        select(Prescription).where(Prescription.patient_id == patient_id).order_by(Prescription.created_at.desc())
    )
    return list(result.scalars().all())


async def build_prescription_pdf(session: AsyncSession, prescription_id: uuid.UUID) -> tuple[bytes, str]:
    """Render an already-saved prescription as a printable PDF. Read-only — the
    prescription, patient and user rows are never modified.

    Returns ``(pdf_bytes, filename)`` where filename is
    ``prescription_<uhid>_<YYYY-MM-DD>.pdf``.
    """
    prescription = await get_prescription(session, prescription_id)
    # `lines` is lazy="selectin" but a session.get() does not trigger it; load
    # explicitly so the PDF builder can iterate without a lazy load.
    await session.refresh(prescription, attribute_names=["lines"])

    patient = await session.get(Patient, prescription.patient_id)
    if patient is None:
        raise NotFoundError("Patient for this prescription no longer exists")
    doctor = await session.get(User, prescription.prescribed_by_id)

    pdf_bytes = render_prescription_pdf(prescription, patient, doctor)

    uhid_slug = re.sub(r"[^A-Za-z0-9._-]+", "-", patient.uhid or "unknown")
    date_slug = prescription.created_at.strftime("%Y-%m-%d")
    filename = f"prescription_{uhid_slug}_{date_slug}.pdf"
    return pdf_bytes, filename

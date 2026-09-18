import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.core.exceptions import NotFoundError
from app.events.bus import EventType, emit
from app.patients.models import (
    DOCUMENT_TYPE_AADHAAR,
    DOCUMENT_TYPE_VISA,
    Couple,
    DocumentVerificationStatus,
    Patient,
    PatientDocument,
    VisaSupportRequest,
)
from app.patients.schemas import (
    CoupleCreate,
    PatientCreate,
    PatientUpdate,
    VisaSupportRequestCreate,
    VisaSupportStatusUpdate,
)


async def generate_uhid(session: AsyncSession) -> str:
    """DAIVF-<year>-<sequence>, matching the existing frontend's UHID format
    (e.g. DAIVF-2026-00428). Sequence is derived from a row count within the
    year rather than a separate counter table, which is fine at this
    hospital's volume; revisit with a dedicated sequence if throughput grows."""
    year = datetime.now(timezone.utc).year
    prefix = f"DAIVF-{year}-"
    result = await session.execute(
        select(Patient.uhid).where(Patient.uhid.like(f"{prefix}%")).order_by(Patient.uhid.desc()).limit(1)
    )
    last = result.scalar_one_or_none()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:05d}"


async def create_patient(
    session: AsyncSession, data: PatientCreate, *, actor_id: uuid.UUID | None = None, actor_role: str | None = None
) -> Patient:
    patient = Patient(uhid=await generate_uhid(session), **data.model_dump())
    session.add(patient)
    await session.flush()

    if actor_id is not None:
        await record_audit_event(
            session, actor_id=actor_id, actor_role=actor_role,
            action="patient.created", entity_type="Patient", entity_id=str(patient.id),
            after_state={"uhid": patient.uhid, "full_name": patient.full_name},
        )
    return patient


async def get_patient(session: AsyncSession, patient_id: uuid.UUID) -> Patient:
    patient = await session.get(Patient, patient_id)
    if not patient:
        raise NotFoundError("Patient not found", error_code="patient_not_found")
    return patient


async def list_patients(session: AsyncSession, *, search: str | None = None, limit: int = 50) -> list[Patient]:
    stmt = select(Patient).order_by(Patient.created_at.desc()).limit(limit)
    if search:
        term = f"%{search.lower()}%"
        stmt = select(Patient).where(
            (Patient.full_name.ilike(term)) | (Patient.uhid.ilike(term)) | (Patient.phone.ilike(term))
        ).order_by(Patient.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_patient(
    session: AsyncSession, patient_id: uuid.UUID, data: PatientUpdate, *, actor_id: uuid.UUID, actor_role: str
) -> Patient:
    patient = await get_patient(session, patient_id)
    before = {"full_name": patient.full_name, "phone": patient.phone, "email": patient.email}

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="patient.updated", entity_type="Patient", entity_id=str(patient.id),
        before_state=before, after_state=data.model_dump(exclude_unset=True, mode="json"),
    )
    return patient


async def create_couple(
    session: AsyncSession, data: CoupleCreate, *, actor_id: uuid.UUID, actor_role: str
) -> Couple:
    female = await create_patient(session, data.female_patient)
    male = await create_patient(session, data.male_patient)

    couple = Couple(
        female_patient_id=female.id,
        male_patient_id=male.id,
        relationship_info=data.relationship_info,
        infertility_type=data.infertility_type,
        infertility_duration=data.infertility_duration,
        previous_iui_cycles=data.previous_iui_cycles,
        previous_ivf_cycles=data.previous_ivf_cycles,
        previous_treatment_notes=data.previous_treatment_notes,
    )
    session.add(couple)
    await session.flush()

    # CoupleOut serialises both partner relationships. A freshly-added object
    # has not been through a SELECT, so lazy="selectin" never fired; without
    # this refresh, response serialisation lazy-loads on the async session and
    # raises MissingGreenlet -> 500 "Could not create the couple".
    await session.refresh(couple, attribute_names=["female_patient", "male_patient"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="couple.created", entity_type="Couple", entity_id=str(couple.id),
        after_state={"female_uhid": female.uhid, "male_uhid": male.uhid},
    )
    await emit(
        session,
        event_type=EventType.PATIENT_REGISTERED,
        entity_type="Couple",
        entity_id=str(couple.id),
        payload={"female_patient_id": str(female.id), "male_patient_id": str(male.id)},
    )
    return couple


async def get_couple_for_patient(session: AsyncSession, patient_id: uuid.UUID) -> Couple | None:
    result = await session.execute(
        select(Couple).where(
            (Couple.female_patient_id == patient_id) | (Couple.male_patient_id == patient_id)
        )
    )
    return result.scalar_one_or_none()


async def get_partner_for_patient(session: AsyncSession, patient_id: uuid.UUID) -> dict | None:
    """The linked partner of one individual patient, or ``None`` if they have no
    couple on record. Raises NotFoundError if ``patient_id`` itself is unknown.

    Reuses the existing Couple relationship (female_patient_id / male_patient_id)
    — no new relationship system. Returns only the partner's own identity; the
    caller still loads the partner's medical records through the normal
    per-patient endpoints, gated by the same permissions."""
    await get_patient(session, patient_id)  # 404 for an invalid patient id

    couple = await get_couple_for_patient(session, patient_id)
    if couple is None:
        return None

    # patient_id may arrive as a str from the path; compare as UUID so the
    # female/male branch is chosen correctly (str != UUID in Python).
    pid = patient_id if isinstance(patient_id, uuid.UUID) else uuid.UUID(str(patient_id))
    if couple.female_patient_id == pid:
        return {
            "couple_id": couple.id,
            "patient_role": "female",
            "partner_role": "male",
            "partner": couple.male_patient,
        }
    return {
        "couple_id": couple.id,
        "patient_role": "male",
        "partner_role": "female",
        "partner": couple.female_patient,
    }


async def get_mandatory_document_status(session: AsyncSession, patient_id: uuid.UUID) -> dict:
    """New requirement (source doc §4/§35 checklist 1-2): Aadhaar mandatory
    for Indian patients, visa mandatory for international patients."""
    patient = await get_patient(session, patient_id)
    required_type = DOCUMENT_TYPE_VISA if patient.is_international else DOCUMENT_TYPE_AADHAAR

    result = await session.execute(
        select(PatientDocument)
        .where(PatientDocument.patient_id == patient_id, PatientDocument.document_type == required_type)
        .order_by(PatientDocument.created_at.desc())
    )
    doc = result.scalars().first()

    return {
        "patient_id": patient_id,
        "required_document_type": required_type,
        "is_uploaded": doc is not None,
        "is_verified": doc is not None and doc.verification_status == DocumentVerificationStatus.VERIFIED,
    }


async def create_visa_support_request(
    session: AsyncSession, data: VisaSupportRequestCreate, *, actor_id: uuid.UUID, actor_role: str
) -> VisaSupportRequest:
    request = VisaSupportRequest(**data.model_dump())
    session.add(request)
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="patients.visa_support_requested", entity_type="VisaSupportRequest", entity_id=str(request.id),
        after_state={"request_type": data.request_type},
    )
    return request


async def list_visa_support_requests(session: AsyncSession, patient_id: uuid.UUID) -> list[VisaSupportRequest]:
    result = await session.execute(
        select(VisaSupportRequest).where(VisaSupportRequest.patient_id == patient_id).order_by(VisaSupportRequest.created_at.desc())
    )
    return list(result.scalars().all())


async def update_visa_support_status(
    session: AsyncSession, request_id: uuid.UUID, data: VisaSupportStatusUpdate, *, actor_id: uuid.UUID, actor_role: str
) -> VisaSupportRequest:
    request = await session.get(VisaSupportRequest, request_id)
    if not request:
        raise NotFoundError("Visa support request not found")

    before = {"status": request.status.value}
    request.status = data.status
    request.handled_by_id = actor_id
    if data.notes:
        request.notes = data.notes
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="patients.visa_support_status_changed", entity_type="VisaSupportRequest", entity_id=str(request.id),
        before_state=before, after_state={"status": data.status.value},
    )
    return request


async def verify_document(
    session: AsyncSession, document_id: uuid.UUID, *, approve: bool, notes: str | None, actor_id: uuid.UUID, actor_role: str
) -> PatientDocument:
    """New requirement (source doc §4) — Aadhaar/visa verification status,
    distinct from the generic upload audit event already recorded by
    documents.py's upload_document endpoint."""
    doc = await session.get(PatientDocument, document_id)
    if not doc:
        raise NotFoundError("Document not found")

    doc.verification_status = DocumentVerificationStatus.VERIFIED if approve else DocumentVerificationStatus.REJECTED
    doc.verified_by_id = actor_id
    doc.verified_at = datetime.now(timezone.utc)
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="patients.document_verified" if approve else "patients.document_rejected",
        entity_type="PatientDocument", entity_id=str(doc.id), reason=notes,
    )
    return doc

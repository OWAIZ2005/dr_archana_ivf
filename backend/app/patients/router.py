from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.patients import service
from app.patients.schemas import (
    CoupleCreate,
    CoupleOut,
    MandatoryDocumentStatus,
    PartnerOut,
    PatientCreate,
    PatientListRow,
    PatientSummary,
    PatientUpdate,
    VisaSupportRequestCreate,
    VisaSupportRequestOut,
    VisaSupportStatusUpdate,
)
from app.users.models import User

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientListRow])
async def list_patients(
    search: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("patients.read")),
) -> list[PatientListRow]:
    return await service.list_patients(session, search=search)


@router.post("", response_model=PatientSummary, status_code=201)
async def create_patient(
    body: PatientCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("patients.create")),
) -> PatientSummary:
    """Single-patient registration — for front-desk walk-ins/phone
    bookings that aren't part of an IVF couple record. Reuses the same
    `create_patient`/UHID-generation service `create_couple` already
    calls twice; this just exposes it directly for the one-patient case."""
    return await service.create_patient(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/{patient_id}/summary", response_model=PatientSummary)
async def get_patient_summary(
    patient_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("patients.read")),
) -> PatientSummary:
    return await service.get_patient(session, patient_id)


@router.get("/{patient_id}/partner", response_model=PartnerOut | None)
async def get_patient_partner(
    patient_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("patients.read")),
) -> PartnerOut | None:
    """The linked partner of one individual patient, for the "View Partner"
    navigation. ``null`` when the patient has no couple on record. Same
    ``patients.read`` gate as viewing any patient's chart."""
    return await service.get_partner_for_patient(session, patient_id)


@router.patch("/{patient_id}", response_model=PatientSummary)
async def update_patient(
    patient_id: str,
    body: PatientUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("patients.update")),
) -> PatientSummary:
    return await service.update_patient(session, patient_id, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/couples", response_model=CoupleOut, status_code=201)
async def create_couple(
    body: CoupleCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("patients.create")),
) -> CoupleOut:
    return await service.create_couple(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/couples/by-patient/{patient_id}", response_model=CoupleOut | None)
async def get_couple_for_patient(
    patient_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("patients.read")),
) -> CoupleOut | None:
    return await service.get_couple_for_patient(session, patient_id)


@router.get("/{patient_id}/mandatory-documents", response_model=MandatoryDocumentStatus)
async def get_mandatory_document_status(
    patient_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("patients.read")),
) -> MandatoryDocumentStatus:
    """New requirement (source doc §4) — Aadhaar mandatory for Indian
    patients, visa mandatory for international patients."""
    return await service.get_mandatory_document_status(session, patient_id)


@router.post("/visa-support", response_model=VisaSupportRequestOut, status_code=201)
async def create_visa_support_request(
    body: VisaSupportRequestCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("patients.update")),
) -> VisaSupportRequestOut:
    return await service.create_visa_support_request(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/{patient_id}/visa-support", response_model=list[VisaSupportRequestOut])
async def list_visa_support_requests(
    patient_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("patients.read")),
) -> list[VisaSupportRequestOut]:
    return await service.list_visa_support_requests(session, patient_id)


@router.post("/visa-support/{request_id}/status", response_model=VisaSupportRequestOut)
async def update_visa_support_status(
    request_id: str,
    body: VisaSupportStatusUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("patients.update")),
) -> VisaSupportRequestOut:
    return await service.update_visa_support_status(session, request_id, body, actor_id=current.id, actor_role=current.role.code)

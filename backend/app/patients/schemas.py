import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.patients.models import DocumentVerificationStatus, VisaSupportStatus


class PatientCreate(BaseModel):
    full_name: str
    date_of_birth: date | None = None
    gender: str
    blood_group: str | None = None
    nationality: str | None = None
    is_international: bool = False
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    occupation: str | None = None
    emergency_contact: str | None = None
    referral_source: str | None = None
    allergies: str | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = None
    nationality: str | None = None
    is_international: bool | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    occupation: str | None = None
    emergency_contact: str | None = None
    allergies: str | None = None
    primary_doctor_id: uuid.UUID | None = None


class VisaSupportRequestCreate(BaseModel):
    patient_id: uuid.UUID
    request_type: str
    notes: str | None = None


class VisaSupportStatusUpdate(BaseModel):
    status: VisaSupportStatus
    notes: str | None = None


class VisaSupportRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    patient_id: uuid.UUID
    request_type: str
    status: VisaSupportStatus
    notes: str | None
    handled_by_id: uuid.UUID | None
    created_at: datetime


class DocumentVerify(BaseModel):
    approve: bool
    notes: str | None = None


class MandatoryDocumentStatus(BaseModel):
    """New requirement (source doc §4/§35 checklist items 1-2) — surfaces
    whether a patient's mandatory document (Aadhaar for Indian patients,
    visa for international patients) has been uploaded and verified.
    Registration itself is not blocked on this (the existing one-shot
    couple-registration flow creates both patient records before any
    document exists) — this is meant to drive a 'registration incomplete'
    checklist/banner in the UI instead. NEEDS HOSPITAL CONFIRMATION on
    whether registration should instead hard-block — see
    NEW_FEATURES_GAP_ANALYSIS.md §1."""
    patient_id: uuid.UUID
    required_document_type: str  # "aadhaar" or "visa"
    is_uploaded: bool
    is_verified: bool


# Purpose-specific response shapes, per spec §9/§32 — never a monolithic
# "everything about this patient" endpoint.

class PatientListRow(BaseModel):
    """Powers GET /patients — matches the frontend's PatientRow shape."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    uhid: str
    full_name: str
    date_of_birth: date | None
    gender: str
    phone: str | None


class PatientSummary(BaseModel):
    """Powers GET /patients/{id}/summary — the Patient 360 header, not the full history."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    uhid: str
    full_name: str
    date_of_birth: date | None
    gender: str
    blood_group: str | None
    nationality: str | None
    is_international: bool
    photo_document_id: uuid.UUID | None
    phone: str | None
    email: str | None
    allergies: str | None
    created_at: datetime


class CoupleCreate(BaseModel):
    female_patient: PatientCreate
    male_patient: PatientCreate
    relationship_info: str | None = None
    infertility_type: str | None = None
    infertility_duration: str | None = None
    previous_iui_cycles: int = 0
    previous_ivf_cycles: int = 0
    previous_treatment_notes: str | None = None


class CoupleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    female_patient: PatientSummary
    male_patient: PatientSummary
    relationship_info: str | None
    infertility_type: str | None
    infertility_duration: str | None


class PartnerOut(BaseModel):
    """Powers GET /patients/{id}/partner — the linked partner of ONE individual
    patient, for the "View Partner" navigation. Carries only the partner's own
    identity (name/UHID/summary); no medical data crosses over. ``null`` when the
    patient has no couple on record."""
    couple_id: uuid.UUID
    patient_role: Literal["female", "male"]   # role of the queried patient in the couple
    partner_role: Literal["female", "male"]   # role of the returned partner
    partner: PatientSummary


class PatientDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_type: str
    original_filename: str
    content_type: str
    size_bytes: int
    signed: bool
    verification_status: DocumentVerificationStatus
    verified_by_id: uuid.UUID | None
    verified_at: datetime | None
    created_at: datetime

"""Patient process monitoring — spec §10-§17. Operational-only: this
reads Appointment / AppointmentStatusEvent (appointments module owns
both) to show how long a patient has been sitting in their current
stage and flags a delay against a configurable per-stage threshold. No
persisted "delay" row — a delay is a live fact about an in-progress
appointment, computed on every read from real transition timestamps, so
it can never go stale the way a materialized snapshot would. The one
thing that *is* written back is a delay reason (spec §14), attached to
the AppointmentStatusEvent that started the current stage.

Deliberately exposes only patient_id, full_name, current stage, and
timestamps — never clinical.read-gated fields (diagnosis, consultation
notes) — per spec §23/§28's "operational visibility, not a medical
decision-making system"."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Integer, String, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.appointments.models import Appointment, AppointmentStatus, AppointmentStatusEvent
from app.audit.service import record_audit_event
from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base, get_db
from app.core.deps import require_permission
from app.core.exceptions import NotFoundError
from app.patients.models import Patient
from app.users.models import User

HOSPITAL_TIMEZONE_OFFSET_HOURS = 5.5  # Asia/Kolkata — matches appointments/service.py's HOSPITAL_TIMEZONE

# The stages spec §10-§17 treats as "in process" (excludes the terminal/
# not-yet-arrived states). A patient's current stage is whichever of
# these their appointment.status currently is.
ACTIVE_STAGES: tuple[AppointmentStatus, ...] = (
    AppointmentStatus.ARRIVED,
    AppointmentStatus.WAITING,
    AppointmentStatus.CONSULTATION,
    AppointmentStatus.INVESTIGATION,
    AppointmentStatus.BILLING,
    AppointmentStatus.PHARMACY,
    AppointmentStatus.FOLLOW_UP,
)

DEFAULT_THRESHOLD_MINUTES: dict[AppointmentStatus, int] = {
    AppointmentStatus.ARRIVED: 15,
    AppointmentStatus.WAITING: 30,
    AppointmentStatus.CONSULTATION: 30,
    AppointmentStatus.INVESTIGATION: 20,
    AppointmentStatus.BILLING: 15,
    AppointmentStatus.PHARMACY: 25,
    AppointmentStatus.FOLLOW_UP: 20,
}

DELAY_REASONS = [
    "Staff unavailable", "High patient volume", "System issue", "Documentation pending",
    "Doctor delay", "Prescription clarification", "Pharmacy queue", "Equipment issue", "Other",
]


class ProcessThreshold(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "hr_process_thresholds"

    stage: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)  # AppointmentStatus.value
    threshold_minutes: Mapped[int] = mapped_column(Integer, nullable=False)


async def get_thresholds(session: AsyncSession) -> dict[AppointmentStatus, int]:
    rows = (await session.execute(select(ProcessThreshold))).scalars().all()
    by_stage = {AppointmentStatus(r.stage): r.threshold_minutes for r in rows}
    return {stage: by_stage.get(stage, default) for stage, default in DEFAULT_THRESHOLD_MINUTES.items()}


async def update_thresholds(session: AsyncSession, values: dict[AppointmentStatus, int], *, actor_id: uuid.UUID, actor_role: str) -> dict[AppointmentStatus, int]:
    for stage, minutes in values.items():
        existing = (await session.execute(select(ProcessThreshold).where(ProcessThreshold.stage == stage.value))).scalar_one_or_none()
        old = existing.threshold_minutes if existing else DEFAULT_THRESHOLD_MINUTES[stage]
        if existing:
            existing.threshold_minutes = minutes
        else:
            session.add(ProcessThreshold(stage=stage.value, threshold_minutes=minutes))
        if old != minutes:
            await record_audit_event(
                session, actor_id=actor_id, actor_role=actor_role, action="hr.process_threshold_updated",
                entity_type="ProcessThreshold", entity_id=stage.value,
                before_state={"threshold_minutes": old}, after_state={"threshold_minutes": minutes},
            )
    await session.flush()
    return await get_thresholds(session)


def _severity(actual_minutes: float, threshold_minutes: int) -> str:
    ratio = actual_minutes / threshold_minutes if threshold_minutes else 0
    if ratio >= 2.0:
        return "critical"
    if ratio >= 1.0:
        return "delayed"
    if ratio >= 0.8:
        return "warning"
    return "normal"


async def _stage_started_at(session: AsyncSession, appointment: Appointment) -> datetime:
    last_event = (await session.execute(
        select(AppointmentStatusEvent)
        .where(AppointmentStatusEvent.appointment_id == appointment.id)
        .order_by(AppointmentStatusEvent.changed_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if last_event:
        return last_event.changed_at
    return appointment.checked_in_at or appointment.created_at


async def get_live_flow(session: AsyncSession, *, today: date) -> list["StageFlowOut"]:
    thresholds = await get_thresholds(session)
    stmt = select(Appointment).where(
        Appointment.status.in_(ACTIVE_STAGES),
        func_date_eq_today(Appointment.scheduled_at, today),
    )
    appointments = (await session.execute(stmt)).scalars().all()

    counts: dict[AppointmentStatus, dict[str, int]] = {s: {"normal": 0, "warning": 0, "delayed": 0, "critical": 0} for s in ACTIVE_STAGES}
    now = datetime.now(timezone.utc)
    for appt in appointments:
        started_at = await _stage_started_at(session, appt)
        minutes = (now - started_at).total_seconds() / 60
        sev = _severity(minutes, thresholds[appt.status])
        counts[appt.status][sev] += 1

    return [
        StageFlowOut(
            stage=stage.value, threshold_minutes=thresholds[stage],
            normal=c["normal"], warning=c["warning"], delayed=c["delayed"], critical=c["critical"],
            total=sum(c.values()),
        )
        for stage, c in counts.items()
    ]


def func_date_eq_today(col, today: date):
    """SQLite-in-tests / Postgres-in-prod-safe 'same calendar day' filter
    without importing func at call sites everywhere — appointments store
    scheduled_at as UTC; this compares the date portion directly rather
    than converting timezone in SQL, matching the simpler (not IST-exact)
    filter already acceptable elsewhere in this read-only monitoring view."""
    from sqlalchemy import cast, Date
    return cast(col, Date) == today


async def get_delays(session: AsyncSession, *, today: date, only_delayed: bool = True) -> list["PatientDelayOut"]:
    thresholds = await get_thresholds(session)
    stmt = (
        select(Appointment, Patient, User)
        .join(Patient, Patient.id == Appointment.patient_id)
        .join(User, User.id == Appointment.doctor_id)
        .where(Appointment.status.in_(ACTIVE_STAGES), func_date_eq_today(Appointment.scheduled_at, today))
    )
    rows = (await session.execute(stmt)).all()

    now = datetime.now(timezone.utc)
    out: list[PatientDelayOut] = []
    for appt, patient, doctor in rows:
        started_at = await _stage_started_at(session, appt)
        actual_minutes = (now - started_at).total_seconds() / 60
        threshold = thresholds[appt.status]
        sev = _severity(actual_minutes, threshold)
        if only_delayed and sev in ("normal", "warning"):
            continue

        last_event = (await session.execute(
            select(AppointmentStatusEvent)
            .where(AppointmentStatusEvent.appointment_id == appt.id)
            .order_by(AppointmentStatusEvent.changed_at.desc()).limit(1)
        )).scalar_one_or_none()

        out.append(PatientDelayOut(
            appointment_id=appt.id, event_id=last_event.id if last_event else None,
            patient_id=patient.id, patient_name=patient.full_name,
            stage=appt.status.value, started_at=started_at,
            threshold_minutes=threshold, actual_minutes=round(actual_minutes),
            delay_minutes=max(0, round(actual_minutes - threshold)),
            severity=sev, doctor_name=doctor.full_name,
            delay_reason=last_event.delay_reason if last_event else None,
        ))
    out.sort(key=lambda d: d.actual_minutes, reverse=True)
    return out


async def set_delay_reason(session: AsyncSession, event_id: uuid.UUID, reason: str, *, actor_id: uuid.UUID, actor_role: str) -> AppointmentStatusEvent:
    event = await session.get(AppointmentStatusEvent, event_id)
    if not event:
        raise NotFoundError("Status event not found")
    event.delay_reason = reason
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role, action="hr.delay_reason_set",
        entity_type="AppointmentStatusEvent", entity_id=str(event.id), after_state={"delay_reason": reason},
    )
    return event


async def get_journey(session: AsyncSession, appointment_id: uuid.UUID) -> list[AppointmentStatusEvent]:
    result = await session.execute(
        select(AppointmentStatusEvent).where(AppointmentStatusEvent.appointment_id == appointment_id).order_by(AppointmentStatusEvent.changed_at)
    )
    return list(result.scalars().all())


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class ThresholdsUpdate(BaseModel):
    thresholds: dict[str, int]  # AppointmentStatus.value -> minutes


class ThresholdsOut(BaseModel):
    thresholds: dict[str, int]


class StageFlowOut(BaseModel):
    stage: str
    threshold_minutes: int
    normal: int
    warning: int
    delayed: int
    critical: int
    total: int


class PatientDelayOut(BaseModel):
    appointment_id: uuid.UUID
    event_id: uuid.UUID | None
    patient_id: uuid.UUID
    patient_name: str
    stage: str
    started_at: datetime
    threshold_minutes: int
    actual_minutes: int
    delay_minutes: int
    severity: str
    doctor_name: str
    delay_reason: str | None


class JourneyEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    from_status: AppointmentStatus
    to_status: AppointmentStatus
    changed_at: datetime
    delay_reason: str | None


class DelayReasonRequest(BaseModel):
    reason: str


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #

router = APIRouter(prefix="/hr/process", tags=["hr-process"])


@router.get("/thresholds", response_model=ThresholdsOut)
async def get_thresholds_endpoint(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.process_read")),
) -> ThresholdsOut:
    thresholds = await get_thresholds(session)
    return ThresholdsOut(thresholds={k.value: v for k, v in thresholds.items()})


@router.put("/thresholds", response_model=ThresholdsOut)
async def update_thresholds_endpoint(
    body: ThresholdsUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.settings_manage")),
) -> ThresholdsOut:
    values = {AppointmentStatus(k): v for k, v in body.thresholds.items()}
    thresholds = await update_thresholds(session, values, actor_id=current.id, actor_role=current.role.code)
    return ThresholdsOut(thresholds={k.value: v for k, v in thresholds.items()})


@router.get("/flow", response_model=list[StageFlowOut])
async def get_flow_endpoint(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.process_read")),
) -> list[StageFlowOut]:
    return await get_live_flow(session, today=datetime.now(timezone.utc).date())


@router.get("/delays", response_model=list[PatientDelayOut])
async def get_delays_endpoint(
    only_delayed: bool = True,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.process_read")),
) -> list[PatientDelayOut]:
    return await get_delays(session, today=datetime.now(timezone.utc).date(), only_delayed=only_delayed)


@router.get("/appointments/{appointment_id}/journey", response_model=list[JourneyEventOut])
async def get_journey_endpoint(
    appointment_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.process_read")),
) -> list[JourneyEventOut]:
    return await get_journey(session, appointment_id)


@router.post("/events/{event_id}/reason", response_model=JourneyEventOut)
async def set_delay_reason_endpoint(
    event_id: uuid.UUID,
    body: DelayReasonRequest,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.process_manage")),
) -> JourneyEventOut:
    return await set_delay_reason(session, event_id, body.reason, actor_id=current.id, actor_role=current.role.code)


@router.get("/delay-reasons", response_model=list[str])
async def list_delay_reasons() -> list[str]:
    return DELAY_REASONS

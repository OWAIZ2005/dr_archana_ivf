from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.appointments import service
from app.appointments.models import AppointmentStatus
from app.appointments.schemas import AppointmentCreate, AppointmentOut, AppointmentStatusUpdate
from app.core.database import get_db
from app.core.deps import require_permission
from app.users.models import User

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=list[AppointmentOut])
async def list_appointments(
    day: date = Query(default_factory=date.today),
    doctor_id: str | None = None,
    status: AppointmentStatus | None = None,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("appointments.read")),
) -> list[AppointmentOut]:
    return await service.list_appointments_for_day(session, day=day, doctor_id=doctor_id, status=status)


@router.get("/by-patient/{patient_id}", response_model=list[AppointmentOut])
async def list_appointments_by_patient(
    patient_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("appointments.read")),
) -> list[AppointmentOut]:
    return await service.list_appointments_for_patient(session, patient_id)


@router.post("", response_model=AppointmentOut, status_code=201)
async def create_appointment(
    body: AppointmentCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("appointments.create")),
) -> AppointmentOut:
    return await service.create_appointment(session, body)


@router.post("/{appointment_id}/check-in", response_model=AppointmentOut)
async def check_in(
    appointment_id: str,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("appointments.checkin")),
) -> AppointmentOut:
    from app.appointments.models import AppointmentStatus as S
    return await service.transition_status(
        session, appointment_id, S.ARRIVED, actor_id=current.id, actor_role=current.role.code
    )


@router.post("/{appointment_id}/status", response_model=AppointmentOut)
async def update_status(
    appointment_id: str,
    body: AppointmentStatusUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("appointments.read")),
) -> AppointmentOut:
    return await service.transition_status(
        session, appointment_id, body.status, actor_id=current.id, actor_role=current.role.code, reason=body.reason
    )

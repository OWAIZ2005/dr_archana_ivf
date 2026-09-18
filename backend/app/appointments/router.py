from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.appointments import service
from app.appointments.models import AppointmentStatus
from app.appointments.schemas import (
    AppointmentBatchCreate,
    AppointmentBatchOut,
    AppointmentBatchUpdate,
    AppointmentCreate,
    AppointmentHistoryOut,
    AppointmentListParams,
    AppointmentOut,
    AppointmentEdit,
    AppointmentReschedule,
    AppointmentStatusUpdate,
    BatchGroupOut,
)
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


@router.get("/batches", response_model=list[AppointmentBatchOut])
async def list_batches(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("appointments.read")),
) -> list[AppointmentBatchOut]:
    batches = await service.list_batches(session, active_only=False)
    return [AppointmentBatchOut.from_model(b) for b in batches]


@router.post("/batches", response_model=AppointmentBatchOut, status_code=201)
async def create_batch(
    body: AppointmentBatchCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("appointments.manage_batches")),
) -> AppointmentBatchOut:
    batch = await service.create_batch(session, body, actor_id=current.id, actor_role=current.role.code)
    return AppointmentBatchOut.from_model(batch)


@router.patch("/batches/{batch_id}", response_model=AppointmentBatchOut)
async def update_batch(
    batch_id: str,
    body: AppointmentBatchUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("appointments.manage_batches")),
) -> AppointmentBatchOut:
    batch = await service.update_batch(session, batch_id, body, actor_id=current.id, actor_role=current.role.code)
    return AppointmentBatchOut.from_model(batch)


@router.get("/today-by-batch", response_model=list[BatchGroupOut])
async def today_by_batch(
    day: date = Query(default_factory=date.today),
    doctor_id: str | None = None,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("appointments.read")),
) -> list[BatchGroupOut]:
    """The front-desk dashboard's primary endpoint — today's (or any given
    day's) appointments already grouped into their configured batches."""
    groups = await service.list_today_grouped_by_batch(session, day=day, doctor_id=doctor_id)
    return [
        BatchGroupOut(
            batch=AppointmentBatchOut.from_model(batch) if batch else None,
            appointments=[AppointmentOut.model_validate(a) for a in appts],
            booked_count=booked, remaining=remaining,
        )
        for batch, appts, booked, remaining in groups
    ]


@router.get("/future", response_model=list[AppointmentOut])
async def future_appointments(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    doctor_id: str | None = Query(default=None),
    status: AppointmentStatus | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("appointments.read")),
) -> list[AppointmentOut]:
    """Future Appointment Details — server-side filtered, defaults to
    "from today onward" excluding cancelled/no-show/completed visits."""
    params = AppointmentListParams(from_date=from_date, to_date=to_date, doctor_id=doctor_id, status=status, q=q)
    return await service.list_future_appointments(session, params)


@router.get("/by-channel", response_model=list[AppointmentOut])
async def appointments_by_channel(
    channel: str = Query(...),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    doctor_id: str | None = Query(default=None),
    status: AppointmentStatus | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("appointments.read")),
) -> list[AppointmentOut]:
    """Backs the Phone Call Appointment history table (channel=phone) —
    unrestricted by date, unlike /future and /closed."""
    params = AppointmentListParams(from_date=from_date, to_date=to_date, doctor_id=doctor_id, status=status, channel=channel, q=q)
    return await service.list_appointments_by_channel(session, params)


@router.get("/closed", response_model=list[AppointmentOut])
async def closed_appointments(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    doctor_id: str | None = Query(default=None),
    status: AppointmentStatus | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("appointments.read")),
) -> list[AppointmentOut]:
    """Closed Appointment List — completed/cancelled/no-show visits,
    retrievable indefinitely (never hard-deleted)."""
    params = AppointmentListParams(from_date=from_date, to_date=to_date, doctor_id=doctor_id, status=status, q=q)
    return await service.list_closed_appointments(session, params)


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


@router.post("/{appointment_id}/not-arrived", response_model=AppointmentOut)
async def not_arrived(
    appointment_id: str,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("appointments.checkin")),
) -> AppointmentOut:
    """Soft flag — starts the front-desk's yellow "awaiting arrival"
    countdown without finalizing the appointment as a no-show. Same
    permission as check-in: whoever can say a patient arrived can also
    say they haven't."""
    return await service.mark_not_arrived(session, appointment_id, actor_id=current.id, actor_role=current.role.code)


@router.post("/{appointment_id}/clear-not-arrived", response_model=AppointmentOut)
async def clear_not_arrived(
    appointment_id: str,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("appointments.checkin")),
) -> AppointmentOut:
    return await service.clear_not_arrived(session, appointment_id, actor_id=current.id, actor_role=current.role.code)


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


@router.patch("/{appointment_id}", response_model=AppointmentOut)
async def edit_appointment(
    appointment_id: str,
    body: AppointmentEdit,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("appointments.create")),
) -> AppointmentOut:
    """Fixes a booking mistake (wrong visit type/doctor) — same
    permission as booking, since it's the same everyday correction, not a
    higher-privilege action. Date/time changes still go through
    /reschedule so the audit trail stays consistent."""
    return await service.edit_appointment(session, appointment_id, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentOut)
async def reschedule(
    appointment_id: str,
    body: AppointmentReschedule,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("appointments.reschedule")),
) -> AppointmentOut:
    return await service.reschedule_appointment(
        session, appointment_id, new_scheduled_at=body.new_scheduled_at, reason=body.reason,
        actor_id=current.id, actor_role=current.role.code,
    )


@router.get("/{appointment_id}/history", response_model=list[AppointmentHistoryOut])
async def appointment_history(
    appointment_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("appointments.read")),
) -> list[AppointmentHistoryOut]:
    return await service.list_appointment_history(session, appointment_id)

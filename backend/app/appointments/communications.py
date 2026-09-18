"""Patient contact log — records that a staff member attempted to reach a
patient (call/email) and what came of it. Never claims a call connected;
it only records that contact was initiated and its outcome, per the
"do not pretend a call happened" requirement. No external telephony/email
vendor is wired in here — the frontend uses tel:/mailto: links and this
endpoint just logs the attempt and outcome a staff member reports back.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.appointments.models import PatientCommunication
from app.appointments.schemas import CommunicationCreate, CommunicationOut
from app.audit.service import record_audit_event
from app.core.database import get_db
from app.core.deps import require_permission
from app.users.models import User

router = APIRouter(prefix="/communications", tags=["communications"])


async def list_communications(
    session: AsyncSession, *, patient_id: uuid.UUID | None = None, appointment_id: uuid.UUID | None = None, limit: int = 200
) -> list[PatientCommunication]:
    stmt = select(PatientCommunication)
    if patient_id:
        stmt = stmt.where(PatientCommunication.patient_id == patient_id)
    if appointment_id:
        stmt = stmt.where(PatientCommunication.appointment_id == appointment_id)
    result = await session.execute(stmt.order_by(PatientCommunication.contacted_at.desc()).limit(limit))
    return list(result.scalars().all())


async def create_communication(
    session: AsyncSession, data: CommunicationCreate, *, actor_id: uuid.UUID, actor_role: str
) -> PatientCommunication:
    comm = PatientCommunication(**data.model_dump(), contacted_by_id=actor_id, contacted_at=datetime.now(timezone.utc))
    session.add(comm)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="communication.recorded", entity_type="PatientCommunication", entity_id=str(comm.id),
        after_state={"channel": comm.channel.value, "outcome": comm.outcome},
    )
    return comm


@router.get("", response_model=list[CommunicationOut])
async def list_communications_endpoint(
    patient_id: str | None = Query(default=None),
    appointment_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("communications.create")),
) -> list[CommunicationOut]:
    return await list_communications(session, patient_id=patient_id, appointment_id=appointment_id)


@router.post("", response_model=CommunicationOut, status_code=201)
async def create_communication_endpoint(
    body: CommunicationCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("communications.create")),
) -> CommunicationOut:
    return await create_communication(session, body, actor_id=current.id, actor_role=current.role.code)

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.nursing import service
from app.nursing.schemas import NursingRecordCreate, NursingRecordOut
from app.users.models import User

router = APIRouter(prefix="/nursing", tags=["nursing"])


@router.post("/records", response_model=NursingRecordOut, status_code=201)
async def create_nursing_record(
    body: NursingRecordCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("nursing.create")),
) -> NursingRecordOut:
    return await service.create_nursing_record(
        session, body, actor_id=current.id, actor_role=current.role.code
    )


@router.get("/patients/{patient_id}/records", response_model=list[NursingRecordOut])
async def list_patient_nursing_records(
    patient_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("nursing.read")),
) -> list[NursingRecordOut]:
    return await service.list_nursing_records_for_patient(session, patient_id)


@router.get("/appointments/{appointment_id}/records", response_model=list[NursingRecordOut])
async def list_appointment_nursing_records(
    appointment_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("nursing.read")),
) -> list[NursingRecordOut]:
    return await service.list_nursing_records_for_appointment(session, appointment_id)

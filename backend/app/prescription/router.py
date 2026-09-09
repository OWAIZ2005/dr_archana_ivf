from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.prescription import service
from app.prescription.schemas import PrescriptionCreate, PrescriptionOut
from app.users.models import User

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


@router.post("", response_model=PrescriptionOut, status_code=201)
async def create_prescription(
    body: PrescriptionCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("clinical.write")),
) -> PrescriptionOut:
    return await service.create_prescription(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/{prescription_id}", response_model=PrescriptionOut)
async def get_prescription(
    prescription_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("clinical.read")),
) -> PrescriptionOut:
    return await service.get_prescription(session, prescription_id)


@router.get("/{prescription_id}/pdf")
async def get_prescription_pdf(
    prescription_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("clinical.read")),
) -> StreamingResponse:
    """Printable PDF of an already-saved prescription. Same ``clinical.read``
    gate as viewing the prescription; read-only, no mutation. Served
    ``inline`` so the browser opens it in a printable view."""
    pdf_bytes, filename = await service.build_prescription_pdf(session, prescription_id)

    def _iter():
        yield pdf_bytes

    return StreamingResponse(
        _iter(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/by-patient/{patient_id}", response_model=list[PrescriptionOut])
async def list_prescriptions(
    patient_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("clinical.read")),
) -> list[PrescriptionOut]:
    return await service.list_prescriptions_for_patient(session, patient_id)

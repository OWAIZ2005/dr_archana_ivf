import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.purchasing import service
from app.purchasing.schemas import (
    GRNCreate,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    VendorCreate,
    VendorOut,
    VendorUpdate,
)
from app.users.models import User

router = APIRouter(prefix="/purchasing", tags=["purchasing"])


@router.get("/vendors", response_model=list[VendorOut])
async def list_vendors(
    include_inactive: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchasing.read")),
) -> list[VendorOut]:
    return await service.list_vendors(session, active_only=not include_inactive)


@router.get("/vendors/{vendor_id}", response_model=VendorOut)
async def get_vendor(
    vendor_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchasing.read")),
) -> VendorOut:
    return await service.get_vendor(session, vendor_id)


@router.post("/vendors", response_model=VendorOut, status_code=201)
async def create_vendor(
    body: VendorCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("purchasing.vendor_manage")),
) -> VendorOut:
    return await service.create_vendor(session, body, actor_id=current.id, actor_role=current.role.code)


@router.patch("/vendors/{vendor_id}", response_model=VendorOut)
async def update_vendor(
    vendor_id: uuid.UUID,
    body: VendorUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("purchasing.vendor_manage")),
) -> VendorOut:
    return await service.update_vendor(session, vendor_id, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/orders", response_model=list[PurchaseOrderOut])
async def list_orders(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchasing.read")),
) -> list[PurchaseOrderOut]:
    return await service.list_purchase_orders(session)


@router.post("/orders", response_model=PurchaseOrderOut, status_code=201)
async def create_request(
    body: PurchaseOrderCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("purchasing.request")),
) -> PurchaseOrderOut:
    return await service.create_purchase_request(session, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/orders/{po_id}/approve", response_model=PurchaseOrderOut)
async def approve(
    po_id: str,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("purchasing.approve")),
) -> PurchaseOrderOut:
    return await service.approve_purchase_order(session, po_id, actor_id=current.id, actor_role=current.role.code)


@router.post("/grn", status_code=201)
async def record_grn(
    body: GRNCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("purchasing.receive")),
) -> dict:
    grn = await service.record_grn(session, body, actor_id=current.id, actor_role=current.role.code)
    return {"id": str(grn.id), "recorded": True}

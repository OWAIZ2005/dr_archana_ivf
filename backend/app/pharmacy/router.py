import uuid

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.idempotency import get_idempotent_response, hash_request_body, store_idempotent_response
from app.pharmacy import service
from app.pharmacy.models import IndentStatus
from app.pharmacy.schemas import (
    AvailableStockOut,
    BatchOut,
    DispenseRequest,
    IndentCreate,
    IndentDeliverRequest,
    IndentOut,
    IndentReturnCreate,
    MedicineAttributeCreate,
    MedicineAttributeOut,
    MedicineAttributeUpdate,
    MedicineCreate,
    MedicineDetailOut,
    MedicineOut,
    MedicineUpdate,
    PurchaseCreate,
    PurchaseOut,
    SaleOut,
    SaleReturnCreate,
    SaleReturnOut,
    StockAdjustmentCreate,
    StockAdjustmentOut,
    StockRowOut,
)
from app.users.models import User

router = APIRouter(prefix="/pharmacy", tags=["pharmacy"])


def _medicine_detail_out(medicine, *, batches: list[BatchOut]) -> MedicineDetailOut:
    """Explicit field construction — NOT `MedicineDetailOut.model_validate`
    — because `Medicine.batches` is a `lazy="selectin"` relationship and
    letting pydantic's from_attributes touch it on an object that hasn't
    had it eagerly loaded triggers a synchronous lazy load outside the
    async greenlet (MissingGreenlet), the same class of bug documented in
    app.assets.service._asset_out."""
    return MedicineDetailOut(
        id=medicine.id, generic_name=medicine.generic_name, brand_name=medicine.brand_name,
        manufacturer=medicine.manufacturer, strength=medicine.strength, dosage_form=medicine.dosage_form,
        category=medicine.category, unit=medicine.unit, hsn_code=medicine.hsn_code,
        gst_percent=medicine.gst_percent, purchase_tax_percent=medicine.purchase_tax_percent,
        reorder_level=medicine.reorder_level, minimum_stock=medicine.minimum_stock,
        maximum_stock=medicine.maximum_stock, medicine_type_id=medicine.medicine_type_id,
        item_code=medicine.item_code, barcode=medicine.barcode, rack_number=medicine.rack_number,
        mrp_paise=medicine.mrp_paise, scheduled_drug=medicine.scheduled_drug, is_active=medicine.is_active,
        batches=batches, total_available=sum(b.quantity_available for b in batches),
        created_at=medicine.created_at, updated_at=medicine.updated_at,
    )


# --------------------------------------------------------------------------- #
# Medicine attributes (configurable lookups, e.g. medicine type)
# --------------------------------------------------------------------------- #

@router.get("/attributes", response_model=list[MedicineAttributeOut])
async def list_attributes(
    attribute_type: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[MedicineAttributeOut]:
    return await service.list_medicine_attributes(session, attribute_type=attribute_type, active_only=not include_inactive)


@router.post("/attributes", response_model=MedicineAttributeOut, status_code=201)
async def create_attribute(
    body: MedicineAttributeCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> MedicineAttributeOut:
    return await service.create_medicine_attribute(session, body, actor_id=current.id, actor_role=current.role.code)


@router.patch("/attributes/{attribute_id}", response_model=MedicineAttributeOut)
async def update_attribute(
    attribute_id: uuid.UUID,
    body: MedicineAttributeUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> MedicineAttributeOut:
    return await service.update_medicine_attribute(session, attribute_id, body, actor_id=current.id, actor_role=current.role.code)


# --------------------------------------------------------------------------- #
# Medicines
# --------------------------------------------------------------------------- #

@router.get("/medicines", response_model=list[MedicineOut])
async def list_medicines(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[MedicineOut]:
    return await service.list_medicines_with_stock(session)


@router.post("/medicines", response_model=MedicineDetailOut, status_code=201)
async def create_medicine(
    body: MedicineCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> MedicineDetailOut:
    medicine = await service.create_medicine(session, body, actor_id=current.id, actor_role=current.role.code)
    await session.refresh(medicine)
    return _medicine_detail_out(medicine, batches=[])


@router.get("/medicines/{medicine_id}", response_model=MedicineDetailOut)
async def get_medicine(
    medicine_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> MedicineDetailOut:
    medicine = await service.get_medicine_detail(session, medicine_id)
    return _medicine_detail_out(medicine, batches=[BatchOut.model_validate(b) for b in medicine.batches])


@router.patch("/medicines/{medicine_id}", response_model=MedicineDetailOut)
async def update_medicine(
    medicine_id: uuid.UUID,
    body: MedicineUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> MedicineDetailOut:
    await service.update_medicine(session, medicine_id, body, actor_id=current.id, actor_role=current.role.code)
    medicine = await service.get_medicine_detail(session, medicine_id)
    return _medicine_detail_out(medicine, batches=[BatchOut.model_validate(b) for b in medicine.batches])


@router.patch("/batches/{batch_id}/expiry", response_model=BatchOut)
async def correct_batch_expiry(
    batch_id: uuid.UUID,
    expiry_date: str = Query(..., description="Corrected expiry date, ISO YYYY-MM-DD"),
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> BatchOut:
    from datetime import date as _date
    batch = await service.update_batch_expiry(
        session, batch_id, expiry_date=_date.fromisoformat(expiry_date), actor_id=current.id, actor_role=current.role.code
    )
    return BatchOut.model_validate(batch)


# --------------------------------------------------------------------------- #
# Dispensing (existing) + sales returns (new)
# --------------------------------------------------------------------------- #

@router.post("/dispense", response_model=SaleOut, status_code=201)
async def dispense(
    body: DispenseRequest,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.dispense")),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> SaleOut:
    """Requires Idempotency-Key — a retried dispense request must never
    deduct stock twice, per spec §33/§34."""
    req_hash = hash_request_body(body.model_dump(mode="json"))
    cached = await get_idempotent_response(session, key=idempotency_key, request_hash=req_hash)
    if cached is not None:
        return SaleOut(**cached)

    sale = await service.dispense(session, body, actor_id=current.id, actor_role=current.role.code)
    out = SaleOut.model_validate(sale)
    await store_idempotent_response(session, key=idempotency_key, request_hash=req_hash, response=out.model_dump(mode="json"))
    return out


@router.get("/sales", response_model=list[SaleOut])
async def list_sales(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[SaleOut]:
    return await service.list_sales(session)


@router.get("/sales/{sale_id}", response_model=SaleOut)
async def get_sale(
    sale_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> SaleOut:
    return await service.get_sale(session, sale_id)


@router.post("/sales/{sale_id}/return", response_model=SaleReturnOut, status_code=201)
async def return_sale(
    sale_id: uuid.UUID,
    body: SaleReturnCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.return")),
) -> SaleReturnOut:
    return await service.create_sale_return(session, sale_id, body, actor_id=current.id, actor_role=current.role.code)


# --------------------------------------------------------------------------- #
# Purchase Entry -> GRN
# --------------------------------------------------------------------------- #

@router.get("/purchases", response_model=list[PurchaseOut])
async def list_purchases(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[PurchaseOut]:
    return await service.list_purchases(session)


@router.post("/purchases", response_model=PurchaseOut, status_code=201)
async def create_purchase(
    body: PurchaseCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.purchase")),
) -> PurchaseOut:
    return await service.create_purchase(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/purchases/{purchase_id}", response_model=PurchaseOut)
async def get_purchase(
    purchase_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> PurchaseOut:
    return await service.get_purchase(session, purchase_id)


@router.post("/purchases/{purchase_id}/receive", response_model=PurchaseOut)
async def receive_purchase(
    purchase_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.purchase")),
) -> PurchaseOut:
    """The GRN step: creates/tops-up MedicineBatch stock from the
    purchase's lines and marks the purchase Completed."""
    return await service.receive_purchase(session, purchase_id, actor_id=current.id, actor_role=current.role.code)


# --------------------------------------------------------------------------- #
# Current stock / manual stock adjustment
# --------------------------------------------------------------------------- #

@router.get("/stock", response_model=list[StockRowOut])
async def current_stock(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[StockRowOut]:
    return await service.list_current_stock(session)


@router.post("/stock/adjust", response_model=StockAdjustmentOut, status_code=201)
async def adjust_stock(
    body: StockAdjustmentCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.adjust")),
) -> StockAdjustmentOut:
    return await service.adjust_stock(session, body, actor_id=current.id, actor_role=current.role.code)


# --------------------------------------------------------------------------- #
# Indents — department/room request -> pharmacist delivery -> optional return
# --------------------------------------------------------------------------- #

@router.get("/indents", response_model=list[IndentOut])
async def list_indents(
    status: IndentStatus | None = Query(default=None),
    department: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[IndentOut]:
    return await service.list_indents(session, status=status, department=department)


@router.post("/indents", response_model=IndentOut, status_code=201)
async def create_indent(
    body: IndentCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.indent_request")),
) -> IndentOut:
    return await service.create_indent(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/indents/{indent_id}", response_model=IndentOut)
async def get_indent(
    indent_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> IndentOut:
    return await service.get_indent(session, indent_id)


@router.get("/indents/stock/available", response_model=list[AvailableStockOut])
async def indent_available_stock(
    medicine_id: list[uuid.UUID] = Query(default=[]),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[AvailableStockOut]:
    """The "check current available stock" step of the indent workflow —
    reuses the same MedicineBatch totals Current Stock is built from."""
    stock = await service.get_available_stock(session, medicine_id)
    return [AvailableStockOut(medicine_id=mid, available=qty) for mid, qty in stock.items()]


@router.post("/indents/{indent_id}/deliver", response_model=IndentOut)
async def deliver_indent(
    indent_id: uuid.UUID,
    body: IndentDeliverRequest,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.indent_deliver")),
) -> IndentOut:
    return await service.deliver_indent(session, indent_id, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/indents/{indent_id}/return", status_code=201)
async def return_indent(
    indent_id: uuid.UUID,
    body: IndentReturnCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.indent_deliver")),
) -> dict:
    r = await service.return_indent(session, indent_id, body, actor_id=current.id, actor_role=current.role.code)
    return {"id": str(r.id), "processed": True}

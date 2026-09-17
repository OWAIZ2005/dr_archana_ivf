import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import record_audit_event
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.events.bus import EventType, emit
from app.inventory.models import InventoryItem, StockMovement, StockMovementType
from app.purchasing.models import GoodsReceiptNote, PurchaseOrder, PurchaseOrderStatus, Vendor
from app.purchasing.schemas import GRNCreate, PurchaseOrderCreate, VendorCreate, VendorUpdate


# --------------------------------------------------------------------------- #
# Vendors
# --------------------------------------------------------------------------- #

async def list_vendors(session: AsyncSession, *, active_only: bool = True) -> list[Vendor]:
    stmt = select(Vendor).order_by(Vendor.name)
    if active_only:
        stmt = stmt.where(Vendor.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def get_vendor(session: AsyncSession, vendor_id: uuid.UUID) -> Vendor:
    vendor = await session.get(Vendor, vendor_id)
    if not vendor:
        raise NotFoundError("Vendor not found", error_code="vendor_not_found")
    return vendor


async def create_vendor(
    session: AsyncSession, data: VendorCreate, *, actor_id: uuid.UUID, actor_role: str
) -> Vendor:
    exists = (
        await session.execute(select(Vendor.id).where(Vendor.account_code == data.account_code))
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("A vendor with that account code already exists.", error_code="vendor_exists")

    vendor = Vendor(**data.model_dump())
    session.add(vendor)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="purchasing.vendor_created", entity_type="Vendor", entity_id=str(vendor.id),
        after_state={"name": vendor.name, "account_code": vendor.account_code},
    )
    return vendor


async def update_vendor(
    session: AsyncSession, vendor_id: uuid.UUID, data: VendorUpdate, *, actor_id: uuid.UUID, actor_role: str
) -> Vendor:
    vendor = await get_vendor(session, vendor_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return vendor
    before = {k: getattr(vendor, k) for k in changes}
    for k, v in changes.items():
        setattr(vendor, k, v)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="purchasing.vendor_updated", entity_type="Vendor", entity_id=str(vendor.id),
        before_state={k: (v.value if hasattr(v, "value") else v) for k, v in before.items()},
        after_state={k: (v.value if hasattr(v, "value") else v) for k, v in changes.items()},
    )
    return vendor


async def list_purchase_orders(session: AsyncSession) -> list[PurchaseOrder]:
    result = await session.execute(select(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()))
    return list(result.scalars().all())


async def _next_po_number(session: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"PO-{year}-"
    result = await session.execute(
        select(PurchaseOrder.po_number).where(PurchaseOrder.po_number.like(f"{prefix}%"))
        .order_by(PurchaseOrder.po_number.desc()).limit(1).with_for_update()
    )
    last = result.scalar_one_or_none()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:05d}"


async def create_purchase_request(
    session: AsyncSession, data: PurchaseOrderCreate, *, actor_id: uuid.UUID, actor_role: str
) -> PurchaseOrder:
    po = PurchaseOrder(po_number=await _next_po_number(session), requested_by_id=actor_id, **data.model_dump())
    session.add(po)
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="purchasing.request_created", entity_type="PurchaseOrder", entity_id=str(po.id),
    )
    return po


async def approve_purchase_order(
    session: AsyncSession, po_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str
) -> PurchaseOrder:
    """Critical action — purchasing.approve permission required at router.
    The approver cannot be the same person who requested it (basic
    separation-of-duties control)."""
    po = await session.get(PurchaseOrder, po_id)
    if not po:
        raise NotFoundError("Purchase order not found")
    if po.status != PurchaseOrderStatus.PENDING_APPROVAL:
        raise ConflictError(f"Cannot approve a PO in status '{po.status.value}'.")
    if po.requested_by_id == actor_id:
        raise ConflictError("The requester cannot approve their own purchase order.", error_code="self_approval_blocked")

    po.status = PurchaseOrderStatus.APPROVED
    po.approved_by_id = actor_id
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="purchasing.order_approved", entity_type="PurchaseOrder", entity_id=str(po.id),
    )
    await emit(
        session, event_type=EventType.PURCHASE_ORDER_APPROVED, entity_type="PurchaseOrder", entity_id=str(po.id),
        payload={"po_number": po.po_number},
    )
    return po


async def record_grn(
    session: AsyncSession, data: GRNCreate, *, actor_id: uuid.UUID, actor_role: str
) -> GoodsReceiptNote:
    """Records goods receipt and — for inventory items — pushes the
    received (non-damaged) quantity into the stock ledger in the SAME
    transaction, so a GRN never exists without its corresponding stock
    movement (spec §16/§33)."""
    po = await session.get(PurchaseOrder, data.purchase_order_id)
    if not po:
        raise NotFoundError("Purchase order not found")
    if po.status not in (PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.DISPATCHED):
        raise ConflictError(f"Cannot receive goods for a PO in status '{po.status.value}'.")

    grn = GoodsReceiptNote(received_by_id=actor_id, **data.model_dump())
    session.add(grn)
    po.status = PurchaseOrderStatus.RECEIVED
    await session.flush()

    usable_qty = data.received_quantity - data.damaged_quantity + data.free_quantity
    if po.inventory_item_id and usable_qty > 0:
        result = await session.execute(
            select(InventoryItem).where(InventoryItem.id == po.inventory_item_id).with_for_update()
        )
        item = result.scalar_one_or_none()
        if item:
            item.stock += usable_qty
            item.last_restocked = data.received_date
            session.add(StockMovement(
                item_id=item.id, movement_type=StockMovementType.RESTOCK, quantity_delta=usable_qty,
                reason=f"GRN for {po.po_number}", performed_by_id=actor_id,
            ))

    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="purchasing.grn_recorded", entity_type="GoodsReceiptNote", entity_id=str(grn.id),
        after_state={"received": data.received_quantity, "damaged": data.damaged_quantity},
    )
    return grn

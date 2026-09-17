"""Purchase Orders — Phase 4. A procurement stage BEFORE Purchase
Entry/GRN: Draft -> Pending Approval -> Approved -> (Partially/Fully)
Received -> Cancelled. Creating, editing or approving a PO NEVER touches
stock; only "Receive" does, and it uses the exact same batch
create-or-top-up rule app.pharmacy.service.receive_purchase uses (a
private copy, not a shared call, so this new stage cannot regress the
already-tested Purchase Entry -> GRN flow).

This is deliberately a pharmacy-specific, multi-line PO — distinct from
app.purchasing.PurchaseOrder, which is a generic single-item PO already
used for non-pharmacy inventory and has no batch/tax/multi-line shape.
Extending that one would risk the working inventory flow it already
serves; Purchase Entry (Phase before this) made the same call for the
same reason.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.audit.service import record_audit_event
from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base, get_db
from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.pharmacy.models import MedicineBatch, PharmacyStockTransaction, StockTransactionType
from app.users.models import User

# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class PurchaseOrderStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    FULLY_RECEIVED = "FULLY_RECEIVED"
    CANCELLED = "CANCELLED"


class PharmacyPurchaseOrder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pharmacy_purchase_orders"

    po_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True)
    po_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PurchaseOrderStatus] = mapped_column(Enum(PurchaseOrderStatus, name="pharmacypurchaseorderstatus"), default=PurchaseOrderStatus.DRAFT, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    items: Mapped[list["PharmacyPurchaseOrderItem"]] = relationship(back_populates="po", lazy="selectin")


class PharmacyPurchaseOrderItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "pharmacy_purchase_order_items"

    po_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pharmacy_purchase_orders.id"), nullable=False, index=True)
    po: Mapped["PharmacyPurchaseOrder"] = relationship(back_populates="items")

    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    ordered_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_rate_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expected_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class POItemIn(BaseModel):
    medicine_id: uuid.UUID
    ordered_quantity: int = Field(gt=0)
    purchase_rate_paise: int = Field(ge=0)
    discount_percent: int = Field(default=0, ge=0, le=100)
    tax_percent: int = Field(default=0, ge=0, le=100)
    expected_expiry: date | None = None
    notes: str | None = None


class POCreate(BaseModel):
    vendor_id: uuid.UUID
    po_date: date
    expected_delivery_date: date | None = None
    payment_terms: str | None = None
    notes: str | None = None
    items: list[POItemIn]


class POUpdate(BaseModel):
    """Draft-only edit — vendor/date/terms/notes and a full item replace."""
    vendor_id: uuid.UUID | None = None
    po_date: date | None = None
    expected_delivery_date: date | None = None
    payment_terms: str | None = None
    notes: str | None = None
    items: list[POItemIn] | None = None


class POItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    medicine_id: uuid.UUID
    ordered_quantity: int
    received_quantity: int
    purchase_rate_paise: int
    discount_percent: int
    tax_percent: int
    expected_expiry: date | None
    notes: str | None


class POOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    po_number: str
    vendor_id: uuid.UUID
    po_date: date
    expected_delivery_date: date | None
    payment_terms: str | None
    notes: str | None
    status: PurchaseOrderStatus
    created_by_id: uuid.UUID
    approved_by_id: uuid.UUID | None
    items: list[POItemOut]
    created_at: datetime
    updated_at: datetime


class POReceiveLine(BaseModel):
    po_item_id: uuid.UUID
    quantity: int = Field(gt=0)
    batch_number: str = Field(min_length=1)
    expiry_date: date
    selling_price_paise: int = Field(ge=0)


class POReceiveRequest(BaseModel):
    lines: list[POReceiveLine]


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #


async def _next_po_number(session: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"PPO-{year}-"
    result = await session.execute(
        select(PharmacyPurchaseOrder.po_number).where(PharmacyPurchaseOrder.po_number.like(f"{prefix}%"))
        .order_by(PharmacyPurchaseOrder.po_number.desc()).limit(1).with_for_update()
    )
    last = result.scalar_one_or_none()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:05d}"


async def create_po(session: AsyncSession, data: POCreate, *, actor_id: uuid.UUID, actor_role: str) -> PharmacyPurchaseOrder:
    if not data.items:
        raise ValidationFailedError("At least one medicine line is required.")
    po = PharmacyPurchaseOrder(
        po_number=await _next_po_number(session), vendor_id=data.vendor_id, po_date=data.po_date,
        expected_delivery_date=data.expected_delivery_date, payment_terms=data.payment_terms, notes=data.notes,
        created_by_id=actor_id,
    )
    session.add(po)
    await session.flush()
    for item in data.items:
        session.add(PharmacyPurchaseOrderItem(po_id=po.id, **item.model_dump()))
    await session.flush()
    await session.refresh(po, attribute_names=["items"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.po_created", entity_type="PharmacyPurchaseOrder", entity_id=str(po.id),
        after_state={"po_number": po.po_number, "line_count": len(data.items)},
    )
    return po


async def list_pos(session: AsyncSession, *, status: PurchaseOrderStatus | None = None, vendor_id: uuid.UUID | None = None) -> list[PharmacyPurchaseOrder]:
    stmt = select(PharmacyPurchaseOrder).order_by(PharmacyPurchaseOrder.created_at.desc())
    if status is not None:
        stmt = stmt.where(PharmacyPurchaseOrder.status == status)
    if vendor_id is not None:
        stmt = stmt.where(PharmacyPurchaseOrder.vendor_id == vendor_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_po(session: AsyncSession, po_id: uuid.UUID) -> PharmacyPurchaseOrder:
    po = await session.get(PharmacyPurchaseOrder, po_id)
    if not po:
        raise NotFoundError("Purchase order not found", error_code="po_not_found")
    return po


async def update_po(session: AsyncSession, po_id: uuid.UUID, data: POUpdate, *, actor_id: uuid.UUID, actor_role: str) -> PharmacyPurchaseOrder:
    po = await get_po(session, po_id)
    if po.status != PurchaseOrderStatus.DRAFT:
        raise ConflictError("Only a Draft purchase order can be edited.", error_code="po_not_draft")

    changes = data.model_dump(exclude_unset=True, exclude={"items"})
    for k, v in changes.items():
        setattr(po, k, v)

    if data.items is not None:
        if not data.items:
            raise ValidationFailedError("At least one medicine line is required.")
        existing = (await session.execute(select(PharmacyPurchaseOrderItem).where(PharmacyPurchaseOrderItem.po_id == po_id))).scalars().all()
        for row in existing:
            await session.delete(row)
        await session.flush()
        for item in data.items:
            session.add(PharmacyPurchaseOrderItem(po_id=po.id, **item.model_dump()))

    await session.flush()
    await session.refresh(po, attribute_names=["items"])
    await session.refresh(po)

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.po_updated", entity_type="PharmacyPurchaseOrder", entity_id=str(po.id),
        after_state={"po_number": po.po_number},
    )
    return po


async def submit_po(session: AsyncSession, po_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str) -> PharmacyPurchaseOrder:
    po = await get_po(session, po_id)
    if po.status != PurchaseOrderStatus.DRAFT:
        raise ConflictError(f"Cannot submit a PO in status '{po.status.value}'.", error_code="po_not_draft")
    po.status = PurchaseOrderStatus.PENDING_APPROVAL
    await session.flush()
    await session.refresh(po)
    return po


async def approve_po(session: AsyncSession, po_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str) -> PharmacyPurchaseOrder:
    po = await get_po(session, po_id)
    if po.status != PurchaseOrderStatus.PENDING_APPROVAL:
        raise ConflictError(f"Cannot approve a PO in status '{po.status.value}'.", error_code="po_not_pending")
    if po.created_by_id == actor_id:
        raise ConflictError("The creator cannot approve their own purchase order.", error_code="self_approval_blocked")
    po.status = PurchaseOrderStatus.APPROVED
    po.approved_by_id = actor_id
    await session.flush()
    await session.refresh(po)

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.po_approved", entity_type="PharmacyPurchaseOrder", entity_id=str(po.id),
        after_state={"po_number": po.po_number},
    )
    return po


async def cancel_po(session: AsyncSession, po_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str) -> PharmacyPurchaseOrder:
    po = await get_po(session, po_id)
    if po.status in (PurchaseOrderStatus.FULLY_RECEIVED, PurchaseOrderStatus.CANCELLED):
        raise ConflictError(f"Cannot cancel a PO in status '{po.status.value}'.", error_code="po_cannot_cancel")
    po.status = PurchaseOrderStatus.CANCELLED
    await session.flush()
    await session.refresh(po)

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.po_cancelled", entity_type="PharmacyPurchaseOrder", entity_id=str(po.id),
        after_state={"po_number": po.po_number},
    )
    return po


def _recompute_po_status(items: list[PharmacyPurchaseOrderItem]) -> PurchaseOrderStatus:
    total_ordered = sum(i.ordered_quantity for i in items)
    total_received = sum(i.received_quantity for i in items)
    if total_received >= total_ordered:
        return PurchaseOrderStatus.FULLY_RECEIVED
    if total_received > 0:
        return PurchaseOrderStatus.PARTIALLY_RECEIVED
    return PurchaseOrderStatus.APPROVED


async def receive_po(session: AsyncSession, po_id: uuid.UUID, data: POReceiveRequest, *, actor_id: uuid.UUID, actor_role: str) -> PharmacyPurchaseOrder:
    """The only step in the PO lifecycle that changes stock. Reuses the
    exact create-or-top-up-batch rule app.pharmacy.service.receive_purchase
    applies for Purchase Entry -> GRN (see that function's own comment for
    why top-up never overwrites an existing batch's rate/expiry)."""
    po = await session.get(PharmacyPurchaseOrder, po_id)
    if not po:
        raise NotFoundError("Purchase order not found", error_code="po_not_found")
    if po.status not in (PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.PARTIALLY_RECEIVED):
        raise ConflictError(f"Cannot receive against a PO in status '{po.status.value}'.", error_code="po_not_receivable")
    if not data.lines:
        raise ValidationFailedError("At least one line is required to receive.")

    items_result = await session.execute(select(PharmacyPurchaseOrderItem).where(PharmacyPurchaseOrderItem.po_id == po_id).with_for_update())
    items_by_id = {i.id: i for i in items_result.scalars().all()}

    now = datetime.now(timezone.utc)
    for line in data.lines:
        item = items_by_id.get(line.po_item_id)
        if not item:
            raise NotFoundError("Purchase order line not found on this PO.", error_code="po_item_not_found")
        remaining = item.ordered_quantity - item.received_quantity
        if line.quantity > remaining:
            raise ValidationFailedError(
                f"Cannot receive {line.quantity} — only {remaining} of this line remain on order.",
                error_code="receive_exceeds_remaining",
            )

        existing_batch = (
            await session.execute(
                select(MedicineBatch).where(
                    MedicineBatch.medicine_id == item.medicine_id, MedicineBatch.batch_number == line.batch_number
                ).with_for_update()
            )
        ).scalar_one_or_none()
        if existing_batch:
            existing_batch.quantity_received += line.quantity
            existing_batch.quantity_available += line.quantity
            batch = existing_batch
        else:
            batch = MedicineBatch(
                medicine_id=item.medicine_id, batch_number=line.batch_number, expiry_date=line.expiry_date,
                purchase_rate_paise=item.purchase_rate_paise, selling_rate_paise=line.selling_price_paise,
                quantity_received=line.quantity, quantity_available=line.quantity,
            )
            session.add(batch)
            await session.flush()

        session.add(PharmacyStockTransaction(
            medicine_id=item.medicine_id, batch_id=batch.id, transaction_type=StockTransactionType.PO_RECEIPT,
            quantity_delta=line.quantity, reference_type="PharmacyPurchaseOrder", reference_id=po_id,
            performed_by_id=actor_id, occurred_at=now,
        ))
        item.received_quantity += line.quantity

    await session.flush()
    await session.refresh(po, attribute_names=["items"])
    po.status = _recompute_po_status(po.items)
    await session.flush()
    await session.refresh(po)

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.po_received", entity_type="PharmacyPurchaseOrder", entity_id=str(po.id),
        after_state={"po_number": po.po_number, "status": po.status.value},
    )
    return po


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #

router = APIRouter(prefix="/pharmacy/purchase-orders", tags=["pharmacy-purchase-orders"])


@router.get("", response_model=list[POOut])
async def list_pos_endpoint(
    status: PurchaseOrderStatus | None = Query(default=None),
    vendor_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[POOut]:
    return await list_pos(session, status=status, vendor_id=vendor_id)


@router.post("", response_model=POOut, status_code=201)
async def create_po_endpoint(
    body: POCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.po_create")),
) -> POOut:
    return await create_po(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/{po_id}", response_model=POOut)
async def get_po_endpoint(
    po_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> POOut:
    return await get_po(session, po_id)


@router.patch("/{po_id}", response_model=POOut)
async def update_po_endpoint(
    po_id: uuid.UUID,
    body: POUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.po_create")),
) -> POOut:
    return await update_po(session, po_id, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/{po_id}/submit", response_model=POOut)
async def submit_po_endpoint(
    po_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.po_create")),
) -> POOut:
    return await submit_po(session, po_id, actor_id=current.id, actor_role=current.role.code)


@router.post("/{po_id}/approve", response_model=POOut)
async def approve_po_endpoint(
    po_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.po_approve")),
) -> POOut:
    return await approve_po(session, po_id, actor_id=current.id, actor_role=current.role.code)


@router.post("/{po_id}/cancel", response_model=POOut)
async def cancel_po_endpoint(
    po_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.po_approve")),
) -> POOut:
    return await cancel_po(session, po_id, actor_id=current.id, actor_role=current.role.code)


@router.post("/{po_id}/receive", response_model=POOut)
async def receive_po_endpoint(
    po_id: uuid.UUID,
    body: POReceiveRequest,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.purchase")),
) -> POOut:
    return await receive_po(session, po_id, body, actor_id=current.id, actor_role=current.role.code)

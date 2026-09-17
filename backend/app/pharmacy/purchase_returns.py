"""Purchase Returns — Phase 3. Returns goods back to a vendor against an
already-received (completed) purchase, decreasing the exact batch stock
that purchase created and recording it in the same
PharmacyStockTransaction ledger Indents write to.

Integrates with the existing PharmacyPurchase / PharmacyPurchaseLine /
MedicineBatch — no parallel purchase or stock system.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.audit.service import record_audit_event
from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base, get_db
from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.pharmacy.models import (
    MedicineBatch,
    PharmacyPurchase,
    PharmacyPurchaseLine,
    PharmacyStockTransaction,
    PurchaseStatus,
    StockTransactionType,
)
from app.users.models import User

# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class PurchaseReturn(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pharmacy_purchase_returns"

    return_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    purchase_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pharmacy_purchases.id"), nullable=False, index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True)
    return_date: Mapped[date] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    items: Mapped[list["PurchaseReturnItem"]] = relationship(back_populates="return_", lazy="selectin")


class PurchaseReturnItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "pharmacy_purchase_return_items"

    return_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pharmacy_purchase_returns.id"), nullable=False, index=True)
    return_: Mapped["PurchaseReturn"] = relationship(back_populates="items")

    purchase_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pharmacy_purchase_lines.id"), nullable=False)
    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicine_batches.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_rate_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_paise: Mapped[int] = mapped_column(Integer, nullable=False)


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class PurchaseReturnLineIn(BaseModel):
    purchase_line_id: uuid.UUID
    quantity: int = Field(gt=0)


class PurchaseReturnCreate(BaseModel):
    reason: str | None = None
    lines: list[PurchaseReturnLineIn]


class PurchaseReturnItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    purchase_line_id: uuid.UUID
    medicine_id: uuid.UUID
    batch_id: uuid.UUID
    quantity: int
    purchase_rate_paise: int
    tax_percent: int
    total_paise: int


class PurchaseReturnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    return_number: str
    purchase_id: uuid.UUID
    vendor_id: uuid.UUID
    return_date: date
    reason: str | None
    items: list[PurchaseReturnItemOut]
    created_at: datetime


class ReturnableLineOut(BaseModel):
    """Purchase-line-level "how much can still be returned" view — the
    module's own worked example: Purchased 100, Previously returned 20,
    Remaining (max new return) 80."""
    purchase_line_id: uuid.UUID
    medicine_id: uuid.UUID
    batch_number: str
    purchased_quantity: int
    already_returned: int
    returnable: int


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #


async def _next_return_number(session: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"PRET-{year}-"
    result = await session.execute(
        select(PurchaseReturn.return_number).where(PurchaseReturn.return_number.like(f"{prefix}%"))
        .order_by(PurchaseReturn.return_number.desc()).limit(1).with_for_update()
    )
    last = result.scalar_one_or_none()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:05d}"


async def get_returnable_lines(session: AsyncSession, purchase_id: uuid.UUID) -> list[ReturnableLineOut]:
    purchase = await session.get(PharmacyPurchase, purchase_id)
    if not purchase:
        raise NotFoundError("Purchase not found", error_code="purchase_not_found")

    lines = (await session.execute(select(PharmacyPurchaseLine).where(PharmacyPurchaseLine.purchase_id == purchase_id))).scalars().all()
    already_returned = dict(
        (await session.execute(
            select(PurchaseReturnItem.purchase_line_id, func.coalesce(func.sum(PurchaseReturnItem.quantity), 0))
            .group_by(PurchaseReturnItem.purchase_line_id)
        )).all()
    )
    out = []
    for line in lines:
        purchased = line.quantity + line.free_quantity
        returned = already_returned.get(line.id, 0)
        out.append(ReturnableLineOut(
            purchase_line_id=line.id, medicine_id=line.medicine_id, batch_number=line.batch_number,
            purchased_quantity=purchased, already_returned=returned, returnable=purchased - returned,
        ))
    return out


async def create_purchase_return(
    session: AsyncSession, purchase_id: uuid.UUID, data: PurchaseReturnCreate, *, actor_id: uuid.UUID, actor_role: str
) -> PurchaseReturn:
    purchase = await session.get(PharmacyPurchase, purchase_id)
    if not purchase:
        raise NotFoundError("Purchase not found", error_code="purchase_not_found")
    if purchase.status != PurchaseStatus.COMPLETED:
        raise ConflictError("Can only return against a completed (received) purchase.", error_code="purchase_not_received")
    if not data.lines:
        raise ValidationFailedError("At least one line is required to process a return.")

    returnable = {r.purchase_line_id: r for r in await get_returnable_lines(session, purchase_id)}

    return_ = PurchaseReturn(
        return_number=await _next_return_number(session), purchase_id=purchase_id, vendor_id=purchase.vendor_id,
        return_date=date.today(), reason=data.reason, created_by_id=actor_id,
    )
    session.add(return_)
    await session.flush()

    now = datetime.now(timezone.utc)
    for req_line in data.lines:
        info = returnable.get(req_line.purchase_line_id)
        if not info:
            raise NotFoundError("Purchase line not found on this purchase.", error_code="purchase_line_not_found")
        if req_line.quantity > info.returnable:
            raise ValidationFailedError(
                f"Cannot return {req_line.quantity} — only {info.returnable} of this line remain returnable.",
                error_code="return_exceeds_purchased",
            )

        purchase_line = await session.get(PharmacyPurchaseLine, req_line.purchase_line_id)
        batch = (
            await session.execute(
                select(MedicineBatch).where(
                    MedicineBatch.medicine_id == purchase_line.medicine_id, MedicineBatch.batch_number == purchase_line.batch_number
                ).with_for_update()
            )
        ).scalar_one_or_none()
        if not batch:
            raise NotFoundError("The batch this purchase created no longer exists.", error_code="batch_not_found")
        if batch.quantity_available < req_line.quantity:
            raise ConflictError(
                f"Only {batch.quantity_available} units of this batch remain in stock — some may already be dispensed/transferred.",
                error_code="insufficient_stock",
            )

        batch.quantity_available -= req_line.quantity
        gross = req_line.quantity * purchase_line.purchase_rate_paise
        tax_amt = gross * purchase_line.tax_percent // 100
        total = gross + tax_amt

        session.add(PurchaseReturnItem(
            return_id=return_.id, purchase_line_id=purchase_line.id, medicine_id=purchase_line.medicine_id,
            batch_id=batch.id, quantity=req_line.quantity, purchase_rate_paise=purchase_line.purchase_rate_paise,
            tax_percent=purchase_line.tax_percent, total_paise=total,
        ))
        session.add(PharmacyStockTransaction(
            medicine_id=purchase_line.medicine_id, batch_id=batch.id, transaction_type=StockTransactionType.PURCHASE_RETURN,
            quantity_delta=-req_line.quantity, reference_type="PurchaseReturn", reference_id=return_.id,
            performed_by_id=actor_id, occurred_at=now,
        ))

    await session.flush()
    await session.refresh(return_, attribute_names=["items"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.purchase_returned", entity_type="PurchaseReturn", entity_id=str(return_.id),
        after_state={"return_number": return_.return_number, "purchase_id": str(purchase_id)},
    )
    return return_


async def list_purchase_returns(session: AsyncSession, *, vendor_id: uuid.UUID | None = None) -> list[PurchaseReturn]:
    stmt = select(PurchaseReturn).order_by(PurchaseReturn.created_at.desc())
    if vendor_id is not None:
        stmt = stmt.where(PurchaseReturn.vendor_id == vendor_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_purchase_return(session: AsyncSession, return_id: uuid.UUID) -> PurchaseReturn:
    r = await session.get(PurchaseReturn, return_id)
    if not r:
        raise NotFoundError("Purchase return not found", error_code="purchase_return_not_found")
    return r


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #

router = APIRouter(prefix="/pharmacy", tags=["pharmacy-purchase-returns"])


@router.get("/purchases/{purchase_id}/returnable", response_model=list[ReturnableLineOut])
async def returnable_lines_endpoint(
    purchase_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[ReturnableLineOut]:
    return await get_returnable_lines(session, purchase_id)


@router.post("/purchases/{purchase_id}/return", response_model=PurchaseReturnOut, status_code=201)
async def create_purchase_return_endpoint(
    purchase_id: uuid.UUID,
    body: PurchaseReturnCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.purchase_return")),
) -> PurchaseReturnOut:
    return await create_purchase_return(session, purchase_id, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/purchase-returns", response_model=list[PurchaseReturnOut])
async def list_purchase_returns_endpoint(
    vendor_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[PurchaseReturnOut]:
    return await list_purchase_returns(session, vendor_id=vendor_id)


@router.get("/purchase-returns/{return_id}", response_model=PurchaseReturnOut)
async def get_purchase_return_endpoint(
    return_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> PurchaseReturnOut:
    return await get_purchase_return(session, return_id)

"""
Pharmacy dispensing — the second highest-stakes transaction in the
system alongside billing payments. Implements spec §33's exact flow:

    Dispense Medicine
        +--> Validate prescription
        +--> Validate stock
        +--> Select batch (FEFO — First Expiry, First Out)
        +--> Deduct stock
        +--> Create dispensing record
        +--> Create billing charge
        +--> Create audit record

All in a single database transaction (the caller's session, committed
by get_db on request success) so a failure partway through — e.g. stock
insufficient on the second line item — rolls back every change already
made, never leaving a half-dispensed, half-billed sale on record.

Row-level locking on MedicineBatch prevents two concurrent dispensing
requests from both reading the same available quantity and both
succeeding, which is exactly how negative inventory happens under load
(spec §33's "Prevent: Negative inventory... Race conditions").
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit_event
from app.core.exceptions import ConflictError, InsufficientStockError, NotFoundError, ValidationFailedError
from app.events.bus import EventType, emit
from app.pharmacy.models import (
    IndentDelivery,
    IndentDeliveryLine,
    IndentItem,
    IndentRequest,
    IndentReturn,
    IndentReturnLine,
    IndentStatus,
    Medicine,
    MedicineAttribute,
    MedicineBatch,
    PaymentMethod,
    PharmacyPurchase,
    PharmacyPurchaseLine,
    PharmacySale,
    PharmacySaleLine,
    PharmacySaleReturn,
    PharmacySaleReturnLine,
    PharmacyStockTransaction,
    PurchaseStatus,
    SaleStatus,
    StockAdjustment,
    StockTransactionType,
)
from app.pharmacy.schemas import (
    DispenseRequest,
    IndentCreate,
    IndentDeliverRequest,
    IndentReturnCreate,
    MedicineAttributeCreate,
    MedicineAttributeUpdate,
    MedicineCreate,
    MedicineUpdate,
    PurchaseCreate,
    SaleReturnCreate,
    StockAdjustmentCreate,
)


async def _next_bill_number(session: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"RX-{year}-"
    result = await session.execute(
        select(PharmacySale.bill_number)
        .where(PharmacySale.bill_number.like(f"{prefix}%"))
        .order_by(PharmacySale.bill_number.desc())
        .limit(1)
        .with_for_update()
    )
    last = result.scalar_one_or_none()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:05d}"


async def _select_fefo_batches(
    session: AsyncSession, *, medicine_id: uuid.UUID, quantity_needed: int
) -> list[tuple[MedicineBatch, int]]:
    """Locks and returns the batches (oldest-expiry-first) needed to cover
    `quantity_needed`, splitting across batches if one alone isn't enough.
    Raises InsufficientStockError if total available across all batches
    can't cover the request."""
    result = await session.execute(
        select(MedicineBatch)
        .where(MedicineBatch.medicine_id == medicine_id, MedicineBatch.quantity_available > 0)
        .order_by(MedicineBatch.expiry_date.asc())
        .with_for_update()
    )
    batches = list(result.scalars().all())

    allocation: list[tuple[MedicineBatch, int]] = []
    remaining = quantity_needed
    for batch in batches:
        if remaining <= 0:
            break
        take = min(batch.quantity_available, remaining)
        allocation.append((batch, take))
        remaining -= take

    if remaining > 0:
        medicine = await session.get(Medicine, medicine_id)
        name = medicine.generic_name if medicine else str(medicine_id)
        raise InsufficientStockError(
            f"Insufficient stock for {name}: requested {quantity_needed}, "
            f"available {quantity_needed - remaining}.",
        )
    return allocation


async def dispense(
    session: AsyncSession, data: DispenseRequest, *, actor_id: uuid.UUID, actor_role: str
) -> PharmacySale:
    if not data.lines:
        raise ValidationFailedError("At least one medicine line is required.")

    bill_number = await _next_bill_number(session)
    sale = PharmacySale(
        bill_number=bill_number,
        patient_id=data.patient_id,
        prescribed_by_id=data.prescribed_by_id,
        dispensed_by_id=actor_id,
        total_amount_paise=0,
    )
    session.add(sale)
    await session.flush()

    total = 0
    low_stock_medicine_ids: list[uuid.UUID] = []

    for line in data.lines:
        allocation = await _select_fefo_batches(session, medicine_id=line.medicine_id, quantity_needed=line.quantity)
        for batch, take_qty in allocation:
            batch.quantity_available -= take_qty
            line_total = batch.selling_rate_paise * take_qty
            total += line_total
            session.add(PharmacySaleLine(
                sale_id=sale.id, medicine_id=line.medicine_id, batch_id=batch.id,
                quantity=take_qty, unit_price_paise=batch.selling_rate_paise,
            ))

        medicine = await session.get(Medicine, line.medicine_id)
        # Direct aggregate query rather than `medicine.batches` — the
        # batches just mutated above were loaded via a separate query in
        # _select_fefo_batches, not through this relationship, so summing
        # via the relationship risks the same under-loaded-instance issue
        # documented in billing/service.py::create_invoice. An explicit
        # SUM is also just the right tool here regardless.
        remaining_result = await session.execute(
            select(func.coalesce(func.sum(MedicineBatch.quantity_available), 0))
            .where(MedicineBatch.medicine_id == medicine.id)
        )
        remaining_stock = remaining_result.scalar_one()
        if remaining_stock <= medicine.reorder_level:
            low_stock_medicine_ids.append(medicine.id)

    if data.discount_paise > total:
        raise ValidationFailedError("Discount cannot exceed the bill's gross amount.", error_code="discount_exceeds_total")

    sale.total_amount_paise = total - data.discount_paise
    sale.discount_paise = data.discount_paise
    sale.payment_method = PaymentMethod(data.payment_method)
    await session.flush()
    # sale.lines were added via raw FK, same pattern as billing's charges —
    # refresh before SaleOut serializes them outside the async context.
    await session.refresh(sale, attribute_names=["lines"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.medicine_dispensed", entity_type="PharmacySale", entity_id=str(sale.id),
        after_state={"bill_number": bill_number, "total_amount_paise": total, "line_count": len(data.lines)},
    )
    await emit(
        session, event_type=EventType.MEDICINE_DISPENSED, entity_type="PharmacySale", entity_id=str(sale.id),
        payload={"patient_id": str(data.patient_id), "total_amount_paise": total},
    )
    for med_id in low_stock_medicine_ids:
        await emit(
            session, event_type=EventType.STOCK_BELOW_REORDER_LEVEL, entity_type="Medicine", entity_id=str(med_id),
            payload={"medicine_id": str(med_id)},
        )

    return sale


async def list_sales(session: AsyncSession, *, limit: int = 100) -> list[PharmacySale]:
    result = await session.execute(select(PharmacySale).order_by(PharmacySale.created_at.desc()).limit(limit))
    return list(result.scalars().all())


async def get_sale(session: AsyncSession, sale_id: uuid.UUID) -> PharmacySale:
    sale = await session.get(PharmacySale, sale_id)
    if not sale:
        raise NotFoundError("Pharmacy sale not found", error_code="sale_not_found")
    return sale


async def list_medicines_with_stock(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Medicine).order_by(Medicine.generic_name))
    medicines = result.scalars().all()
    return [
        {
            "id": m.id, "generic_name": m.generic_name, "brand_name": m.brand_name,
            "category": m.category, "unit": m.unit, "reorder_level": m.reorder_level,
            "total_available": sum(b.quantity_available for b in m.batches),
        }
        for m in medicines
    ]


# --------------------------------------------------------------------------- #
# Medicine attributes
# --------------------------------------------------------------------------- #

async def list_medicine_attributes(
    session: AsyncSession, *, attribute_type: str | None = None, active_only: bool = True
) -> list[MedicineAttribute]:
    stmt = select(MedicineAttribute).order_by(MedicineAttribute.attribute_type, MedicineAttribute.name)
    if attribute_type:
        stmt = stmt.where(MedicineAttribute.attribute_type == attribute_type)
    if active_only:
        stmt = stmt.where(MedicineAttribute.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def create_medicine_attribute(
    session: AsyncSession, data: MedicineAttributeCreate, *, actor_id: uuid.UUID, actor_role: str
) -> MedicineAttribute:
    exists = (
        await session.execute(
            select(MedicineAttribute.id).where(
                MedicineAttribute.attribute_type == data.attribute_type,
                MedicineAttribute.name == data.name,
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("That attribute value already exists.", error_code="attribute_exists")

    attr = MedicineAttribute(**data.model_dump())
    session.add(attr)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.attribute_created", entity_type="MedicineAttribute", entity_id=str(attr.id),
        after_state={"attribute_type": attr.attribute_type, "name": attr.name},
    )
    return attr


async def update_medicine_attribute(
    session: AsyncSession, attribute_id: uuid.UUID, data: MedicineAttributeUpdate, *, actor_id: uuid.UUID, actor_role: str
) -> MedicineAttribute:
    attr = await session.get(MedicineAttribute, attribute_id)
    if not attr:
        raise NotFoundError("Attribute not found", error_code="attribute_not_found")
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(attr, k, v)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.attribute_updated", entity_type="MedicineAttribute", entity_id=str(attr.id),
        after_state=changes,
    )
    return attr


# --------------------------------------------------------------------------- #
# Medicine CRUD (catalogue — not stock; see MedicineBatch for stock)
# --------------------------------------------------------------------------- #

async def create_medicine(
    session: AsyncSession, data: MedicineCreate, *, actor_id: uuid.UUID, actor_role: str
) -> Medicine:
    if data.barcode:
        exists = (
            await session.execute(select(Medicine.id).where(Medicine.barcode == data.barcode))
        ).scalar_one_or_none()
        if exists is not None:
            raise ConflictError("A medicine with that barcode already exists.", error_code="barcode_exists")

    medicine = Medicine(**data.model_dump())
    session.add(medicine)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.medicine_created", entity_type="Medicine", entity_id=str(medicine.id),
        after_state={"generic_name": medicine.generic_name, "brand_name": medicine.brand_name},
    )
    return medicine


async def get_medicine_detail(session: AsyncSession, medicine_id: uuid.UUID) -> Medicine:
    result = await session.execute(
        select(Medicine).options(selectinload(Medicine.batches)).where(Medicine.id == medicine_id)
    )
    medicine = result.scalar_one_or_none()
    if not medicine:
        raise NotFoundError("Medicine not found", error_code="medicine_not_found")
    return medicine


async def update_medicine(
    session: AsyncSession, medicine_id: uuid.UUID, data: MedicineUpdate, *, actor_id: uuid.UUID, actor_role: str
) -> Medicine:
    """Every field here — name, manufacturer, pricing, tax, HSN, stock
    limits, active/inactive — is editable after the record is created; the
    module's "editing is first-class" requirement. Only the append-only
    ledgers (batches, sales, purchases) are correction-only, never edited
    in place."""
    medicine = await session.get(Medicine, medicine_id)
    if not medicine:
        raise NotFoundError("Medicine not found", error_code="medicine_not_found")
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return medicine
    before = {k: getattr(medicine, k) for k in changes}
    for k, v in changes.items():
        setattr(medicine, k, v)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.medicine_updated", entity_type="Medicine", entity_id=str(medicine.id),
        before_state={k: (v.value if hasattr(v, "value") else v) for k, v in before.items()},
        after_state={k: (v.value if hasattr(v, "value") else v) for k, v in changes.items()},
    )
    return medicine


async def update_batch_expiry(
    session: AsyncSession, batch_id: uuid.UUID, *, expiry_date: date, actor_id: uuid.UUID, actor_role: str
) -> MedicineBatch:
    """Correcting a mis-keyed expiry date (the module spec's exact
    example: "10/09/2026" entered instead of "10/09/2027") without
    touching quantities or rates."""
    batch = await session.get(MedicineBatch, batch_id)
    if not batch:
        raise NotFoundError("Batch not found", error_code="batch_not_found")
    before = batch.expiry_date
    batch.expiry_date = expiry_date
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.batch_expiry_corrected", entity_type="MedicineBatch", entity_id=str(batch.id),
        before_state={"expiry_date": before.isoformat()}, after_state={"expiry_date": expiry_date.isoformat()},
    )
    return batch


# --------------------------------------------------------------------------- #
# Purchase Entry -> GRN (receive)
# --------------------------------------------------------------------------- #

async def _next_purchase_number(session: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"PUR-{year}-"
    result = await session.execute(
        select(PharmacyPurchase.purchase_number)
        .where(PharmacyPurchase.purchase_number.like(f"{prefix}%"))
        .order_by(PharmacyPurchase.purchase_number.desc()).limit(1).with_for_update()
    )
    last = result.scalar_one_or_none()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:05d}"


def _line_totals(line) -> tuple[int, int, int, int]:
    """Returns (gross, tax_amount, total) for one purchase line — never
    hardcoded, always derived from qty/rate/discount/tax on the line."""
    gross = line.quantity * line.purchase_rate_paise
    discount_amt = gross * line.discount_percent // 100
    taxable = gross - discount_amt
    tax_amt = taxable * line.tax_percent // 100
    total = taxable + tax_amt
    return gross, tax_amt, total, discount_amt


async def create_purchase(
    session: AsyncSession, data: PurchaseCreate, *, actor_id: uuid.UUID, actor_role: str
) -> PharmacyPurchase:
    if not data.lines:
        raise ValidationFailedError("At least one medicine line is required.")

    purchase = PharmacyPurchase(
        purchase_number=await _next_purchase_number(session),
        vendor_id=data.vendor_id, invoice_number=data.invoice_number,
        invoice_date=data.invoice_date, entry_date=data.entry_date,
        created_by_id=actor_id,
    )
    session.add(purchase)
    await session.flush()

    taxable_total = tax_total = discount_total = net_total = 0
    for line in data.lines:
        gross, tax_amt, total, discount_amt = _line_totals(line)
        taxable_total += gross - discount_amt
        tax_total += tax_amt
        discount_total += discount_amt
        net_total += total
        session.add(PharmacyPurchaseLine(
            purchase_id=purchase.id, medicine_id=line.medicine_id, batch_number=line.batch_number,
            quantity=line.quantity, free_quantity=line.free_quantity,
            purchase_rate_paise=line.purchase_rate_paise, selling_price_paise=line.selling_price_paise,
            discount_percent=line.discount_percent, expiry_date=line.expiry_date, hsn_code=line.hsn_code,
            tax_percent=line.tax_percent, gross_amount_paise=gross, total_value_paise=total,
        ))

    purchase.taxable_value_paise = taxable_total
    purchase.cgst_paise = tax_total // 2
    purchase.sgst_paise = tax_total - purchase.cgst_paise
    purchase.total_discount_paise = discount_total
    purchase.total_value_paise = net_total
    await session.flush()
    await session.refresh(purchase, attribute_names=["lines"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.purchase_created", entity_type="PharmacyPurchase", entity_id=str(purchase.id),
        after_state={"purchase_number": purchase.purchase_number, "total_value_paise": net_total},
    )
    return purchase


async def list_purchases(session: AsyncSession) -> list[PharmacyPurchase]:
    result = await session.execute(select(PharmacyPurchase).order_by(PharmacyPurchase.created_at.desc()))
    return list(result.scalars().all())


async def get_purchase(session: AsyncSession, purchase_id: uuid.UUID) -> PharmacyPurchase:
    purchase = await session.get(PharmacyPurchase, purchase_id)
    if not purchase:
        raise NotFoundError("Purchase not found", error_code="purchase_not_found")
    return purchase


async def receive_purchase(
    session: AsyncSession, purchase_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str
) -> PharmacyPurchase:
    """The GRN step — the ONLY place new MedicineBatch stock is created
    outside tests/seeding. Matches an existing (medicine_id, batch_number)
    batch if one exists (top-up), otherwise creates a new batch row."""
    purchase = await session.get(PharmacyPurchase, purchase_id)
    if not purchase:
        raise NotFoundError("Purchase not found", error_code="purchase_not_found")
    if purchase.status != PurchaseStatus.PENDING:
        raise ConflictError(f"Cannot receive a purchase in status '{purchase.status.value}'.")

    lines_result = await session.execute(
        select(PharmacyPurchaseLine).where(PharmacyPurchaseLine.purchase_id == purchase.id)
    )
    lines = list(lines_result.scalars().all())

    for line in lines:
        usable_qty = line.quantity + line.free_quantity
        existing = (
            await session.execute(
                select(MedicineBatch)
                .where(MedicineBatch.medicine_id == line.medicine_id, MedicineBatch.batch_number == line.batch_number)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if existing:
            # Top up quantity only — the batch's original rate/expiry stay
            # as first recorded (append-only economics); a genuinely
            # different rate or expiry should be entered under its own
            # batch number rather than silently rewriting history.
            existing.quantity_received += usable_qty
            existing.quantity_available += usable_qty
        else:
            session.add(MedicineBatch(
                medicine_id=line.medicine_id, batch_number=line.batch_number, expiry_date=line.expiry_date,
                purchase_rate_paise=line.purchase_rate_paise, selling_rate_paise=line.selling_price_paise,
                quantity_received=usable_qty, quantity_available=usable_qty,
            ))

    purchase.status = PurchaseStatus.COMPLETED
    purchase.received_by_id = actor_id
    purchase.received_at = datetime.now(timezone.utc)
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.purchase_received", entity_type="PharmacyPurchase", entity_id=str(purchase.id),
        after_state={"purchase_number": purchase.purchase_number, "lines": len(lines)},
    )
    await emit(
        session, event_type=EventType.PHARMACY_STOCK_RECEIVED,
        entity_type="PharmacyPurchase", entity_id=str(purchase.id),
        payload={"purchase_number": purchase.purchase_number},
    )
    await session.refresh(purchase, attribute_names=["lines"])
    return purchase


# --------------------------------------------------------------------------- #
# Sales returns
# --------------------------------------------------------------------------- #

async def create_sale_return(
    session: AsyncSession, sale_id: uuid.UUID, data: SaleReturnCreate, *, actor_id: uuid.UUID, actor_role: str
) -> PharmacySaleReturn:
    if not data.lines:
        raise ValidationFailedError("At least one line is required to process a return.")

    sale = await session.get(PharmacySale, sale_id)
    if not sale:
        raise NotFoundError("Pharmacy sale not found", error_code="sale_not_found")
    if sale.status == SaleStatus.RETURNED:
        raise ConflictError("This sale has already been fully returned.")

    # How much of each original sale-line has already been returned.
    already_returned: dict[uuid.UUID, int] = {}
    prior = await session.execute(
        select(PharmacySaleReturnLine.sale_line_id, func.coalesce(func.sum(PharmacySaleReturnLine.quantity), 0))
        .join(PharmacySaleReturn, PharmacySaleReturn.id == PharmacySaleReturnLine.return_id)
        .where(PharmacySaleReturn.sale_id == sale_id)
        .group_by(PharmacySaleReturnLine.sale_line_id)
    )
    for line_id, qty in prior.all():
        already_returned[line_id] = qty

    return_ = PharmacySaleReturn(sale_id=sale_id, processed_by_id=actor_id, reason=data.reason, total_refund_paise=0)
    session.add(return_)
    await session.flush()

    total_refund = 0
    for req_line in data.lines:
        sale_line = await session.get(PharmacySaleLine, req_line.sale_line_id)
        if not sale_line or sale_line.sale_id != sale_id:
            raise NotFoundError("Sale line not found on this bill.", error_code="sale_line_not_found")
        max_returnable = sale_line.quantity - already_returned.get(sale_line.id, 0)
        if req_line.quantity > max_returnable:
            raise ValidationFailedError(
                f"Cannot return {req_line.quantity} — only {max_returnable} of this line remain returnable.",
                error_code="return_quantity_exceeds_sold",
            )

        batch = (
            await session.execute(select(MedicineBatch).where(MedicineBatch.id == sale_line.batch_id).with_for_update())
        ).scalar_one_or_none()
        if batch:
            batch.quantity_available += req_line.quantity

        refund_amount = req_line.quantity * sale_line.unit_price_paise
        total_refund += refund_amount
        session.add(PharmacySaleReturnLine(
            return_id=return_.id, sale_line_id=sale_line.id, batch_id=sale_line.batch_id,
            medicine_id=sale_line.medicine_id, quantity=req_line.quantity, refund_amount_paise=refund_amount,
        ))
        already_returned[sale_line.id] = already_returned.get(sale_line.id, 0) + req_line.quantity

    return_.total_refund_paise = total_refund
    total_sold = sum(l.quantity for l in (await session.execute(
        select(PharmacySaleLine).where(PharmacySaleLine.sale_id == sale_id)
    )).scalars().all())
    total_now_returned = sum(already_returned.values())
    sale.status = SaleStatus.RETURNED if total_now_returned >= total_sold else SaleStatus.PARTIALLY_RETURNED
    await session.flush()
    await session.refresh(return_, attribute_names=["lines"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.sale_returned", entity_type="PharmacySaleReturn", entity_id=str(return_.id),
        after_state={"sale_id": str(sale_id), "total_refund_paise": total_refund},
    )
    await emit(
        session, event_type=EventType.PHARMACY_SALE_RETURNED, entity_type="PharmacySaleReturn", entity_id=str(return_.id),
        payload={"sale_id": str(sale_id), "total_refund_paise": total_refund},
    )
    return return_


# --------------------------------------------------------------------------- #
# Current stock / manual stock adjustment
# --------------------------------------------------------------------------- #

async def list_current_stock(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(MedicineBatch, Medicine)
        .join(Medicine, Medicine.id == MedicineBatch.medicine_id)
        .order_by(MedicineBatch.expiry_date.asc())
    )
    today = date.today()
    rows = []
    for batch, medicine in result.all():
        if batch.quantity_available <= 0:
            status = "out_of_stock"
        elif batch.expiry_date < today:
            status = "expired"
        elif (batch.expiry_date - today).days <= 90:
            status = "expiring_soon"
        elif batch.quantity_available <= medicine.minimum_stock:
            status = "low_stock"
        else:
            status = "in_stock"
        rows.append({
            "batch_id": batch.id, "medicine_id": medicine.id, "medicine_name": medicine.brand_name or medicine.generic_name,
            "unit": medicine.unit, "batch_number": batch.batch_number, "expiry_date": batch.expiry_date,
            "quantity_available": batch.quantity_available, "minimum_stock": medicine.minimum_stock,
            "maximum_stock": medicine.maximum_stock, "selling_rate_paise": batch.selling_rate_paise, "status": status,
        })
    return rows


async def adjust_stock(
    session: AsyncSession, data: StockAdjustmentCreate, *, actor_id: uuid.UUID, actor_role: str
) -> StockAdjustment:
    batch = (
        await session.execute(select(MedicineBatch).where(MedicineBatch.id == data.batch_id).with_for_update())
    ).scalar_one_or_none()
    if not batch:
        raise NotFoundError("Batch not found", error_code="batch_not_found")

    system_stock = batch.quantity_available
    difference = data.physical_stock - system_stock
    batch.quantity_available = data.physical_stock

    adjustment = StockAdjustment(
        batch_id=batch.id, medicine_id=batch.medicine_id, system_stock=system_stock,
        physical_stock=data.physical_stock, difference=difference, reason=data.reason, adjusted_by_id=actor_id,
    )
    session.add(adjustment)
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.stock_adjusted", entity_type="MedicineBatch", entity_id=str(batch.id),
        before_state={"quantity_available": system_stock}, after_state={"quantity_available": data.physical_stock},
    )
    return adjustment


# --------------------------------------------------------------------------- #
# Indents — department/room request -> pharmacist review -> delivery -> stock
# transfer, with an optional return path. Delivery reuses the exact FEFO
# batch-selection helper dispensing uses (`_select_fefo_batches`) — indents
# are not a second stock-deduction engine.
# --------------------------------------------------------------------------- #

async def _next_indent_number(session: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"IND-{year}-"
    result = await session.execute(
        select(IndentRequest.indent_number).where(IndentRequest.indent_number.like(f"{prefix}%"))
        .order_by(IndentRequest.indent_number.desc()).limit(1).with_for_update()
    )
    last = result.scalar_one_or_none()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:05d}"


async def create_indent(
    session: AsyncSession, data: IndentCreate, *, actor_id: uuid.UUID, actor_role: str
) -> IndentRequest:
    if not data.items:
        raise ValidationFailedError("At least one medicine line is required.")

    indent = IndentRequest(
        indent_number=await _next_indent_number(session), department=data.department, room=data.room,
        request_date=data.request_date, requested_by_id=actor_id, notes=data.notes,
    )
    session.add(indent)
    await session.flush()

    for item in data.items:
        session.add(IndentItem(
            indent_id=indent.id, medicine_id=item.medicine_id,
            requested_quantity=item.requested_quantity, notes=item.notes,
        ))
    await session.flush()
    await session.refresh(indent, attribute_names=["items"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.indent_created", entity_type="IndentRequest", entity_id=str(indent.id),
        after_state={"indent_number": indent.indent_number, "department": indent.department, "line_count": len(data.items)},
    )
    return indent


async def list_indents(session: AsyncSession, *, status: IndentStatus | None = None, department: str | None = None) -> list[IndentRequest]:
    stmt = select(IndentRequest).order_by(IndentRequest.created_at.desc())
    if status is not None:
        stmt = stmt.where(IndentRequest.status == status)
    if department:
        stmt = stmt.where(IndentRequest.department.ilike(f"%{department}%"))
    return list((await session.execute(stmt)).scalars().all())


async def get_indent(session: AsyncSession, indent_id: uuid.UUID) -> IndentRequest:
    indent = await session.get(IndentRequest, indent_id)
    if not indent:
        raise NotFoundError("Indent not found", error_code="indent_not_found")
    return indent


async def get_available_stock(session: AsyncSession, medicine_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not medicine_ids:
        return {}
    rows = await session.execute(
        select(MedicineBatch.medicine_id, func.coalesce(func.sum(MedicineBatch.quantity_available), 0))
        .where(MedicineBatch.medicine_id.in_(medicine_ids))
        .group_by(MedicineBatch.medicine_id)
    )
    return {mid: qty for mid, qty in rows.all()}


def _recompute_indent_status(items: list[IndentItem]) -> IndentStatus:
    total_requested = sum(i.requested_quantity for i in items)
    total_delivered = sum(i.delivered_quantity for i in items)
    if total_delivered == 0:
        return IndentStatus.PENDING
    if total_delivered >= total_requested:
        return IndentStatus.DELIVERED
    return IndentStatus.PARTIALLY_DELIVERED


async def deliver_indent(
    session: AsyncSession, indent_id: uuid.UUID, data: IndentDeliverRequest, *, actor_id: uuid.UUID, actor_role: str
) -> IndentRequest:
    indent = await session.get(IndentRequest, indent_id)
    if not indent:
        raise NotFoundError("Indent not found", error_code="indent_not_found")
    if indent.status in (IndentStatus.CANCELLED, IndentStatus.DELIVERED):
        raise ConflictError(f"Cannot deliver against an indent in status '{indent.status.value}'.")
    if not data.lines:
        raise ValidationFailedError("At least one line is required to deliver.")

    items_result = await session.execute(select(IndentItem).where(IndentItem.indent_id == indent_id).with_for_update())
    items_by_id = {i.id: i for i in items_result.scalars().all()}

    delivery = IndentDelivery(indent_id=indent_id, delivered_by_id=actor_id, notes=data.notes)
    session.add(delivery)
    await session.flush()

    now = datetime.now(timezone.utc)
    for line in data.lines:
        item = items_by_id.get(line.indent_item_id)
        if not item:
            raise NotFoundError("Indent line not found on this indent.", error_code="indent_item_not_found")

        remaining_requested = item.requested_quantity - item.delivered_quantity
        if line.quantity > remaining_requested:
            raise ValidationFailedError(
                f"Cannot deliver {line.quantity} — only {remaining_requested} of this line remain requested.",
                error_code="delivery_exceeds_requested",
            )

        # Reuses dispensing's FEFO allocator — raises InsufficientStockError
        # (409) if the pharmacy genuinely doesn't have enough on hand; the
        # pharmacist then delivers a smaller quantity instead (partial).
        allocation = await _select_fefo_batches(session, medicine_id=item.medicine_id, quantity_needed=line.quantity)
        for batch, take_qty in allocation:
            batch.quantity_available -= take_qty
            session.add(IndentDeliveryLine(delivery_id=delivery.id, indent_item_id=item.id, batch_id=batch.id, quantity=take_qty))
            session.add(PharmacyStockTransaction(
                medicine_id=item.medicine_id, batch_id=batch.id, transaction_type=StockTransactionType.INDENT_DELIVERY,
                quantity_delta=-take_qty, reference_type="IndentRequest", reference_id=indent_id,
                performed_by_id=actor_id, occurred_at=now,
            ))
        item.delivered_quantity += line.quantity

    await session.flush()
    await session.refresh(indent, attribute_names=["items"])
    indent.status = _recompute_indent_status(indent.items)
    await session.flush()
    # `updated_at` is server-generated (onupdate=func.now()) — the flush
    # above expires it on this object; refresh before the response is
    # serialized outside the async context (same pattern as PharmacySale).
    await session.refresh(indent)

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.indent_delivered", entity_type="IndentRequest", entity_id=str(indent.id),
        after_state={"indent_number": indent.indent_number, "status": indent.status.value},
    )
    return indent


async def return_indent(
    session: AsyncSession, indent_id: uuid.UUID, data: IndentReturnCreate, *, actor_id: uuid.UUID, actor_role: str
) -> IndentReturn:
    indent = await session.get(IndentRequest, indent_id)
    if not indent:
        raise NotFoundError("Indent not found", error_code="indent_not_found")
    if not data.lines:
        raise ValidationFailedError("At least one line is required to process a return.")

    items_result = await session.execute(select(IndentItem).where(IndentItem.indent_id == indent_id).with_for_update())
    items_by_id = {i.id: i for i in items_result.scalars().all()}

    return_ = IndentReturn(indent_id=indent_id, processed_by_id=actor_id, reason=data.reason)
    session.add(return_)
    await session.flush()

    now = datetime.now(timezone.utc)
    for line in data.lines:
        item = items_by_id.get(line.indent_item_id)
        if not item:
            raise NotFoundError("Indent line not found on this indent.", error_code="indent_item_not_found")

        remaining_returnable = item.delivered_quantity - item.returned_quantity
        if line.quantity > remaining_returnable:
            raise ValidationFailedError(
                f"Cannot return {line.quantity} — only {remaining_returnable} of this line remain returnable.",
                error_code="return_exceeds_delivered",
            )

        # Restore into the medicine's FEFO-earliest batch with room, mirroring
        # how a sales return picks a batch — there's no requirement the
        # returned units go back to the exact batch they were drawn from,
        # only that total on-hand stock is correctly restored.
        batch = (
            await session.execute(
                select(MedicineBatch).where(MedicineBatch.medicine_id == item.medicine_id)
                .order_by(MedicineBatch.expiry_date.asc()).limit(1).with_for_update()
            )
        ).scalar_one_or_none()
        if not batch:
            raise NotFoundError("No batch exists for this medicine to return stock into.", error_code="batch_not_found")

        batch.quantity_available += line.quantity
        session.add(IndentReturnLine(return_id=return_.id, indent_item_id=item.id, batch_id=batch.id, quantity=line.quantity))
        session.add(PharmacyStockTransaction(
            medicine_id=item.medicine_id, batch_id=batch.id, transaction_type=StockTransactionType.INDENT_RETURN,
            quantity_delta=line.quantity, reference_type="IndentRequest", reference_id=indent_id,
            performed_by_id=actor_id, occurred_at=now,
        ))
        item.returned_quantity += line.quantity

    await session.flush()
    await session.refresh(indent, attribute_names=["items"])
    total_delivered = sum(i.delivered_quantity for i in indent.items)
    total_returned = sum(i.returned_quantity for i in indent.items)
    if total_delivered > 0 and total_returned >= total_delivered:
        indent.status = IndentStatus.RETURNED
    await session.flush()
    # Same server-generated updated_at expiry as deliver_indent — refresh
    # both objects before any later request in this session serializes them.
    await session.refresh(indent)
    await session.refresh(return_, attribute_names=["lines"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.indent_returned", entity_type="IndentReturn", entity_id=str(return_.id),
        after_state={"indent_id": str(indent_id)},
    )
    return return_

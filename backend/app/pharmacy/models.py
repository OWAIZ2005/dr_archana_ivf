"""
Pharmacy domain: Medicine (catalogue) -> MedicineBatch (stock, FEFO) ->
PharmacySale (dispensing transaction), from spec §15.

Extended for the Pharmacy Management module (medicine attributes, vendor
purchase -> GRN -> stock, sales returns, stock adjustment). All additions
are additive to the existing dispensing flow above — FEFO dispensing,
idempotency and audit on PharmacySale/MedicineBatch are unchanged.
"""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class MedicineAttribute(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Configurable lookup values (medicine type, etc.) — spec's "Medicine
    Attributes". Deliberately data, not a hardcoded enum, so staff can add
    a new medicine type (e.g. "Suppository") without a code change."""
    __tablename__ = "medicine_attributes"
    __table_args__ = (UniqueConstraint("attribute_type", "name", name="uq_medicine_attribute_type_name"),)

    attribute_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # e.g. "medicine_type"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class Medicine(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "medicines"

    generic_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    strength: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dosage_form: Mapped[str | None] = mapped_column(String(64), nullable=True)  # injection, tablet, ...
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)  # Pen, Vial, Strip, ...
    hsn_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gst_percent: Mapped[int] = mapped_column(Integer, default=12)  # sales tax
    purchase_tax_percent: Mapped[int] = mapped_column(Integer, default=12)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0)
    minimum_stock: Mapped[int] = mapped_column(Integer, default=0)
    maximum_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Medicine form's remaining sections (§ "Medicine Form" of the module spec).
    medicine_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medicine_attributes.id"), nullable=True, index=True
    )
    medicine_type: Mapped["MedicineAttribute | None"] = relationship(lazy="raise_on_sql")
    item_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    rack_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mrp_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_drug: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    batches: Mapped[list["MedicineBatch"]] = relationship(back_populates="medicine", lazy="selectin")


class MedicineBatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "medicine_batches"

    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False, index=True)
    medicine: Mapped["Medicine"] = relationship(back_populates="batches")

    batch_number: Mapped[str] = mapped_column(String(64), nullable=False)
    manufacturing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # FEFO ordering key
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)

    purchase_rate_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    selling_rate_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False)  # decremented on dispense, never negative


class SaleStatus(str, enum.Enum):
    DISPENSED = "dispensed"
    RETURNED = "returned"
    PARTIALLY_RETURNED = "partially_returned"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    CHEQUE = "cheque"
    ONLINE = "online"


class PharmacySale(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pharmacy_sales"

    bill_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    prescribed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    dispensed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)
    # Net amount actually charged (gross line total minus discount_paise) —
    # the figure the Sales Dashboard sums as "Total Sales".
    total_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Named explicitly — app.billing already defines its own unrelated
    # "paymentmethod" Postgres enum type; this avoids a name collision.
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="paymentmethod_pharmacy"), default=PaymentMethod.CASH
    )
    status: Mapped[SaleStatus] = mapped_column(Enum(SaleStatus), default=SaleStatus.DISPENSED)

    lines: Mapped[list["PharmacySaleLine"]] = relationship(back_populates="sale", lazy="selectin")
    payments: Mapped[list["PharmacySalePayment"]] = relationship(back_populates="sale", lazy="selectin")


class PharmacySaleLine(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "pharmacy_sale_lines"

    sale_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pharmacy_sales.id"), nullable=False)
    sale: Mapped["PharmacySale"] = relationship(back_populates="lines")

    # Per-medicine discount, applied on top of the batch's selling rate
    # before the bill-level discount_paise is subtracted — lets a
    # pharmacist discount one line item (e.g. a promo) without touching
    # the rest of the bill.
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicine_batches.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)


class PharmacySalePayment(Base, UUIDPrimaryKeyMixin):
    """One or more payment rows per sale — lets a bill be split across
    methods (e.g. part card, part cash) instead of forcing a single method
    for the whole amount. A non-split bill still gets exactly one row here,
    so the frontend always reads the breakdown from the same place."""
    __tablename__ = "pharmacy_sale_payments"

    sale_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pharmacy_sales.id"), nullable=False, index=True)
    sale: Mapped["PharmacySale"] = relationship(back_populates="payments")

    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, name="paymentmethod_pharmacy"), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)


# --------------------------------------------------------------------------- #
# Purchase Entry -> GRN. A vendor-sourced, multi-line, tax-aware purchase —
# richer than the generic single-item app.purchasing.PurchaseOrder (which
# stays as-is for non-pharmacy inventory). Receiving a purchase is the ONLY
# way new MedicineBatch stock enters the system outside of tests/seeding.
# --------------------------------------------------------------------------- #

class PurchaseStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIALLY_RECEIVED = "partially_received"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PharmacyPurchase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pharmacy_purchases"

    purchase_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True)
    invoice_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PurchaseStatus] = mapped_column(Enum(PurchaseStatus), default=PurchaseStatus.PENDING, index=True)

    taxable_value_paise: Mapped[int] = mapped_column(Integer, default=0)
    cgst_paise: Mapped[int] = mapped_column(Integer, default=0)
    sgst_paise: Mapped[int] = mapped_column(Integer, default=0)
    total_discount_paise: Mapped[int] = mapped_column(Integer, default=0)
    total_value_paise: Mapped[int] = mapped_column(Integer, default=0)  # Net Total (Purchase Summary)

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    received_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["PharmacyPurchaseLine"]] = relationship(back_populates="purchase", lazy="selectin")


class PharmacyPurchaseLine(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "pharmacy_purchase_lines"

    purchase_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pharmacy_purchases.id"), nullable=False, index=True)
    purchase: Mapped["PharmacyPurchase"] = relationship(back_populates="lines")

    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    free_quantity: Mapped[int] = mapped_column(Integer, default=0)
    purchase_rate_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    selling_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    hsn_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tax_percent: Mapped[int] = mapped_column(Integer, default=0)
    gross_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)  # qty * rate, before discount/tax
    total_value_paise: Mapped[int] = mapped_column(Integer, nullable=False)  # after discount, plus tax


# --------------------------------------------------------------------------- #
# Sales returns — reverses a PharmacySaleLine, restoring the exact batch it
# came from. Never edits the original sale (finalized transaction); this is
# the "correction/reversal workflow" the spec requires for finalized sales.
# --------------------------------------------------------------------------- #

class PharmacySaleReturn(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pharmacy_sale_returns"

    sale_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pharmacy_sales.id"), nullable=False, index=True)
    processed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    total_refund_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    lines: Mapped[list["PharmacySaleReturnLine"]] = relationship(back_populates="return_", lazy="selectin")


class PharmacySaleReturnLine(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "pharmacy_sale_return_lines"

    return_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pharmacy_sale_returns.id"), nullable=False, index=True)
    return_: Mapped["PharmacySaleReturn"] = relationship(back_populates="lines")

    sale_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pharmacy_sale_lines.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicine_batches.id"), nullable=False)
    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    refund_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)


# --------------------------------------------------------------------------- #
# Manual stock reconciliation (physical count vs system count).
# --------------------------------------------------------------------------- #

class StockAdjustment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Append-only, like app.inventory.StockMovement — MedicineBatch's
    running `quantity_available` is a cache; every change to it away from
    the FEFO dispense/receive/return paths is explained by one of these."""
    __tablename__ = "pharmacy_stock_adjustments"

    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicine_batches.id"), nullable=False, index=True)
    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    system_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    physical_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    difference: Mapped[int] = mapped_column(Integer, nullable=False)  # physical - system, signed
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjusted_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)


# --------------------------------------------------------------------------- #
# Generic pharmacy stock ledger — every indent delivery/return writes one of
# these (spec's "Stock Integrity" requirement for the new Indent flow).
# Existing flows (purchase receive, dispense, sales return, stock adjustment)
# already have their own equally-complete audit trail (PurchaseLine /
# SaleLine / StockAdjustment rows + the audit_events table) and are NOT
# retrofitted to also write here — that would touch tested, shipped code
# for no functional gain, which the brief explicitly says not to risk.
# --------------------------------------------------------------------------- #

class StockTransactionType(str, enum.Enum):
    INDENT_DELIVERY = "INDENT_DELIVERY"
    INDENT_RETURN = "INDENT_RETURN"
    PURCHASE_RETURN = "PURCHASE_RETURN"
    PO_RECEIPT = "PO_RECEIPT"


class PharmacyStockTransaction(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "pharmacy_stock_transactions"

    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicine_batches.id"), nullable=False, index=True)
    transaction_type: Mapped[StockTransactionType] = mapped_column(Enum(StockTransactionType, name="pharmacystocktransactiontype"), nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)  # signed: +in, -out
    reference_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "IndentRequest"
    reference_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    performed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# --------------------------------------------------------------------------- #
# Indents — a hospital department/room's internal request to the pharmacy.
# --------------------------------------------------------------------------- #

class IndentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARTIALLY_DELIVERED = "PARTIALLY_DELIVERED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


class IndentRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "indent_requests"

    indent_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    room: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[IndentStatus] = mapped_column(Enum(IndentStatus, name="indentstatus"), default=IndentStatus.PENDING, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["IndentItem"]] = relationship(back_populates="indent", lazy="selectin")


class IndentItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "indent_items"

    indent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("indent_requests.id"), nullable=False, index=True)
    indent: Mapped["IndentRequest"] = relationship(back_populates="items")

    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    delivered_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    returned_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class IndentDelivery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Header for one delivery event against an indent — an indent can be
    delivered across several of these (each partial fulfilment)."""
    __tablename__ = "indent_deliveries"

    indent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("indent_requests.id"), nullable=False, index=True)
    delivered_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    lines: Mapped[list["IndentDeliveryLine"]] = relationship(back_populates="delivery", lazy="selectin")


class IndentDeliveryLine(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "indent_delivery_lines"

    delivery_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("indent_deliveries.id"), nullable=False, index=True)
    delivery: Mapped["IndentDelivery"] = relationship(back_populates="lines")

    indent_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("indent_items.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicine_batches.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class IndentReturn(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "indent_returns"

    indent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("indent_requests.id"), nullable=False, index=True)
    processed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    lines: Mapped[list["IndentReturnLine"]] = relationship(back_populates="return_", lazy="selectin")


class IndentReturnLine(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "indent_return_lines"

    return_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("indent_returns.id"), nullable=False, index=True)
    return_: Mapped["IndentReturn"] = relationship(back_populates="lines")

    indent_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("indent_items.id"), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicine_batches.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class VendorMedicineCatalog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A vendor's declared product catalogue — separate from purchase
    history. Purchase history (PharmacyPurchaseLine) only tells you what has
    been bought before; this table lets a pharmacist explicitly mark a
    medicine as available/unavailable from a given vendor (e.g. the vendor
    has told them it's out of stock or discontinued), independent of
    whether anything has ever been purchased from them."""
    __tablename__ = "vendor_medicine_catalog"
    __table_args__ = (UniqueConstraint("vendor_id", "medicine_id", name="uq_vendor_medicine_catalog"),)

    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True)
    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False, index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

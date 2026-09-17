"""
Purchase Request -> Approval -> Purchase Order -> GRN -> Stock Entry,
per spec §16.

``Vendor`` was added for the Pharmacy Management module — it lives here
(not in app.pharmacy) because a vendor can supply any purchasable item,
not only medicines; app.pharmacy.PharmacyPurchase references it by FK.
"""
import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class VendorPaymentType(str, enum.Enum):
    CREDIT = "credit"
    CASH = "cash"
    CARD = "card"
    CHEQUE = "cheque"
    RTGS = "rtgs"
    TRANSACTION = "transaction"


class Vendor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "vendors"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    account_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    payment_type: Mapped[VendorPaymentType] = mapped_column(Enum(VendorPaymentType), default=VendorPaymentType.CREDIT)
    credit_period_days: Mapped[int] = mapped_column(Integer, default=0)
    purchase_limit_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_to_deliver: Mapped[int | None] = mapped_column(Integer, nullable=True)

    bank_account_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ifsc_code: Mapped[str | None] = mapped_column(String(16), nullable=True)

    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class PurchaseOrderStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DISPATCHED = "dispatched"
    RECEIVED = "received"
    REJECTED = "rejected"


class PurchaseOrder(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    item_description: Mapped[str] = mapped_column(String(255), nullable=False)
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=True)
    medicine_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=True)

    supplier: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    requested_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[PurchaseOrderStatus] = mapped_column(Enum(PurchaseOrderStatus), default=PurchaseOrderStatus.PENDING_APPROVAL, index=True)

    grn: Mapped["GoodsReceiptNote | None"] = relationship(back_populates="purchase_order", lazy="selectin", uselist=False)


class GoodsReceiptNote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "goods_receipt_notes"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False, unique=True)
    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="grn")

    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    damaged_quantity: Mapped[int] = mapped_column(Integer, default=0)
    free_quantity: Mapped[int] = mapped_column(Integer, default=0)
    supplier_invoice_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

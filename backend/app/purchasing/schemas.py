import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

from app.purchasing.models import PurchaseOrderStatus, VendorPaymentType


class VendorCreate(BaseModel):
    name: str
    account_code: str
    city: str | None = None
    gst_number: str | None = None
    payment_type: VendorPaymentType = VendorPaymentType.CREDIT
    credit_period_days: int = 0
    purchase_limit_paise: int | None = None
    days_to_deliver: int | None = None
    bank_account_number: str | None = None
    bank_name: str | None = None
    ifsc_code: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    address: str | None = None


class VendorUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    gst_number: str | None = None
    payment_type: VendorPaymentType | None = None
    credit_period_days: int | None = None
    purchase_limit_paise: int | None = None
    days_to_deliver: int | None = None
    bank_account_number: str | None = None
    bank_name: str | None = None
    ifsc_code: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    address: str | None = None
    is_active: bool | None = None


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    account_code: str
    city: str | None
    gst_number: str | None
    payment_type: VendorPaymentType
    credit_period_days: int
    purchase_limit_paise: int | None
    days_to_deliver: int | None
    bank_account_number: str | None
    bank_name: str | None
    ifsc_code: str | None
    contact_phone: str | None
    contact_email: str | None
    address: str | None
    is_active: bool


class PurchaseOrderCreate(BaseModel):
    item_description: str
    inventory_item_id: uuid.UUID | None = None
    medicine_id: uuid.UUID | None = None
    supplier: str
    quantity_ordered: int
    amount_paise: int


class PurchaseOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    po_number: str
    item_description: str
    supplier: str
    quantity_ordered: int
    amount_paise: int
    status: PurchaseOrderStatus


class GRNCreate(BaseModel):
    purchase_order_id: uuid.UUID
    received_quantity: int
    damaged_quantity: int = 0
    free_quantity: int = 0
    supplier_invoice_number: str | None = None
    received_date: date
    notes: str | None = None

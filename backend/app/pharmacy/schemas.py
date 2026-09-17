import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.pharmacy.models import IndentStatus, PurchaseStatus


# --------------------------------------------------------------------------- #
# Medicine attributes (configurable lookups, e.g. "medicine_type")
# --------------------------------------------------------------------------- #

class MedicineAttributeCreate(BaseModel):
    attribute_type: str
    name: str
    description: str | None = None


class MedicineAttributeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class MedicineAttributeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    attribute_type: str
    name: str
    description: str | None
    is_active: bool


# --------------------------------------------------------------------------- #
# Medicine
# --------------------------------------------------------------------------- #

class MedicineCreate(BaseModel):
    generic_name: str
    brand_name: str | None = None
    manufacturer: str | None = None
    strength: str | None = None
    dosage_form: str | None = None
    category: str | None = None
    unit: str
    hsn_code: str | None = None
    gst_percent: int = 12
    purchase_tax_percent: int = 12
    reorder_level: int = 0
    minimum_stock: int = 0
    maximum_stock: int | None = None
    medicine_type_id: uuid.UUID | None = None
    item_code: str | None = None
    barcode: str | None = None
    rack_number: str | None = None
    mrp_paise: int | None = None
    scheduled_drug: bool = False

    @field_validator("gst_percent", "purchase_tax_percent")
    @classmethod
    def _tax_in_range(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("Tax percent must be between 0 and 100.")
        return v

    @field_validator("reorder_level", "minimum_stock")
    @classmethod
    def _not_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Cannot be negative.")
        return v


class MedicineUpdate(BaseModel):
    generic_name: str | None = None
    brand_name: str | None = None
    manufacturer: str | None = None
    strength: str | None = None
    dosage_form: str | None = None
    category: str | None = None
    unit: str | None = None
    hsn_code: str | None = None
    gst_percent: int | None = None
    purchase_tax_percent: int | None = None
    reorder_level: int | None = None
    minimum_stock: int | None = None
    maximum_stock: int | None = None
    medicine_type_id: uuid.UUID | None = None
    item_code: str | None = None
    barcode: str | None = None
    rack_number: str | None = None
    mrp_paise: int | None = None
    scheduled_drug: bool | None = None
    is_active: bool | None = None


class MedicineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    generic_name: str
    brand_name: str | None
    category: str | None
    unit: str
    reorder_level: int
    total_available: int = 0


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    batch_number: str
    expiry_date: date
    quantity_available: int
    selling_rate_paise: int


class DispenseLine(BaseModel):
    medicine_id: uuid.UUID
    quantity: int = Field(gt=0)


class DispenseRequest(BaseModel):
    patient_id: uuid.UUID
    prescribed_by_id: uuid.UUID | None = None
    lines: list[DispenseLine]
    create_invoice: bool = True
    discount_paise: int = Field(default=0, ge=0)
    payment_method: str = "cash"

    @field_validator("payment_method")
    @classmethod
    def _valid_payment_method(cls, v: str) -> str:
        allowed = {"cash", "card", "cheque", "online"}
        if v not in allowed:
            raise ValueError(f"payment_method must be one of {sorted(allowed)}")
        return v


class SaleLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    medicine_id: uuid.UUID
    batch_id: uuid.UUID
    quantity: int
    unit_price_paise: int


class SaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    bill_number: str
    patient_id: uuid.UUID
    prescribed_by_id: uuid.UUID | None
    total_amount_paise: int
    discount_paise: int
    payment_method: str
    status: str
    created_at: datetime
    lines: list[SaleLineOut]


class MedicineDetailOut(BaseModel):
    """Full record for the Medicine detail/edit view — every field a user
    can correct, per the module's "editing is first-class" requirement."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    generic_name: str
    brand_name: str | None
    manufacturer: str | None
    strength: str | None
    dosage_form: str | None
    category: str | None
    unit: str
    hsn_code: str | None
    gst_percent: int
    purchase_tax_percent: int
    reorder_level: int
    minimum_stock: int
    maximum_stock: int | None
    medicine_type_id: uuid.UUID | None
    item_code: str | None
    barcode: str | None
    rack_number: str | None
    mrp_paise: int | None
    scheduled_drug: bool
    is_active: bool
    batches: list[BatchOut] = []
    total_available: int = 0
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Purchase Entry -> GRN
# --------------------------------------------------------------------------- #

class PurchaseLineCreate(BaseModel):
    medicine_id: uuid.UUID
    batch_number: str
    quantity: int = Field(gt=0)
    free_quantity: int = Field(default=0, ge=0)
    purchase_rate_paise: int = Field(ge=0)
    selling_price_paise: int = Field(ge=0)
    discount_percent: int = Field(default=0, ge=0, le=100)
    expiry_date: date
    hsn_code: str | None = None
    tax_percent: int = Field(default=0, ge=0, le=100)


class PurchaseCreate(BaseModel):
    vendor_id: uuid.UUID
    invoice_number: str | None = None
    invoice_date: date | None = None
    entry_date: date
    lines: list[PurchaseLineCreate]


class PurchaseLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    medicine_id: uuid.UUID
    batch_number: str
    quantity: int
    free_quantity: int
    purchase_rate_paise: int
    selling_price_paise: int
    discount_percent: int
    expiry_date: date
    hsn_code: str | None
    tax_percent: int
    gross_amount_paise: int
    total_value_paise: int


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    purchase_number: str
    vendor_id: uuid.UUID
    invoice_number: str | None
    invoice_date: date | None
    entry_date: date
    status: PurchaseStatus
    taxable_value_paise: int
    cgst_paise: int
    sgst_paise: int
    total_discount_paise: int
    total_value_paise: int
    received_at: datetime | None
    lines: list[PurchaseLineOut]


# --------------------------------------------------------------------------- #
# Sales returns
# --------------------------------------------------------------------------- #

class SaleReturnLineCreate(BaseModel):
    sale_line_id: uuid.UUID
    quantity: int = Field(gt=0)


class SaleReturnCreate(BaseModel):
    reason: str | None = None
    lines: list[SaleReturnLineCreate]


class SaleReturnLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sale_line_id: uuid.UUID
    medicine_id: uuid.UUID
    batch_id: uuid.UUID
    quantity: int
    refund_amount_paise: int


class SaleReturnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sale_id: uuid.UUID
    reason: str | None
    total_refund_paise: int
    lines: list[SaleReturnLineOut]


# --------------------------------------------------------------------------- #
# Stock / stock adjustment
# --------------------------------------------------------------------------- #

class StockRowOut(BaseModel):
    """One batch row for the Current Stock screen."""
    batch_id: uuid.UUID
    medicine_id: uuid.UUID
    medicine_name: str
    unit: str
    batch_number: str
    expiry_date: date
    quantity_available: int
    minimum_stock: int
    maximum_stock: int | None
    selling_rate_paise: int
    status: str  # in_stock | low_stock | out_of_stock | expiring_soon | expired


class StockAdjustmentCreate(BaseModel):
    batch_id: uuid.UUID
    physical_stock: int = Field(ge=0)
    reason: str | None = None


class StockAdjustmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    batch_id: uuid.UUID
    medicine_id: uuid.UUID
    system_stock: int
    physical_stock: int
    difference: int
    reason: str | None
    adjusted_by_id: uuid.UUID
    created_at: datetime


# --------------------------------------------------------------------------- #
# Indents
# --------------------------------------------------------------------------- #

class IndentItemCreate(BaseModel):
    medicine_id: uuid.UUID
    requested_quantity: int = Field(gt=0)
    notes: str | None = None


class IndentCreate(BaseModel):
    department: str = Field(min_length=1)
    room: str | None = None
    request_date: date
    notes: str | None = None
    items: list[IndentItemCreate]


class IndentItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    medicine_id: uuid.UUID
    requested_quantity: int
    delivered_quantity: int
    returned_quantity: int
    notes: str | None


class IndentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    indent_number: str
    department: str
    room: str | None
    request_date: date
    requested_by_id: uuid.UUID
    status: IndentStatus
    notes: str | None
    items: list[IndentItemOut]
    created_at: datetime
    updated_at: datetime


class IndentDeliverLine(BaseModel):
    indent_item_id: uuid.UUID
    quantity: int = Field(gt=0)


class IndentDeliverRequest(BaseModel):
    notes: str | None = None
    lines: list[IndentDeliverLine]


class IndentReturnLineIn(BaseModel):
    indent_item_id: uuid.UUID
    quantity: int = Field(gt=0)


class IndentReturnCreate(BaseModel):
    reason: str | None = None
    lines: list[IndentReturnLineIn]


class AvailableStockOut(BaseModel):
    """Per-medicine available quantity — the "check stock before
    delivering" step of the indent workflow."""
    medicine_id: uuid.UUID
    available: int

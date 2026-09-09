import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.assets.models import AssetStatus


# --------------------------------- Location ---------------------------------- #

class LocationCreate(BaseModel):
    name: str
    building: str | None = None
    floor: str | None = None
    description: str | None = None
    in_charge: str | None = None
    phone: str | None = None


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    building: str | None
    floor: str | None
    description: str | None
    in_charge: str | None
    phone: str | None
    is_active: bool


# ---------------------------------- Asset ----------------------------------- #

class AssetCreate(BaseModel):
    name: str
    current_location_id: uuid.UUID
    category: str | None = None
    brand: str | None = None
    model: str | None = None
    serial_number: str | None = None
    purchase_date: date | None = None
    cost_paise: int | None = None
    warranty_until: date | None = None
    amc_until: date | None = None


class AssetUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    brand: str | None = None
    model: str | None = None
    serial_number: str | None = None
    status: AssetStatus | None = None
    warranty_until: date | None = None
    amc_until: date | None = None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    asset_code: str
    name: str
    category: str | None
    brand: str | None
    model: str | None
    serial_number: str | None
    status: AssetStatus
    qr_token: str
    current_location: LocationOut | None
    updated_at: datetime


class AssetDetailOut(AssetOut):
    purchase_date: date | None
    cost_paise: int | None
    warranty_until: date | None
    amc_until: date | None
    registered_by_id: uuid.UUID | None
    created_at: datetime


class AssetMoveRequest(BaseModel):
    to_location_id: uuid.UUID
    note: str | None = None


class AssetMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_type: str
    from_location: LocationOut | None
    to_location: LocationOut | None
    note: str | None
    moved_by_id: uuid.UUID
    moved_by_name: str | None
    moved_at: datetime

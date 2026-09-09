"""QR-coded physical asset register + immutable movement history, spec §20.

V1 asset-tracking extension:
  * ``Location`` — the venue master; assets/movements reference it by FK.
  * ``Asset.current_location_id`` / ``AssetMovement.from_location_id`` /
    ``AssetMovement.to_location_id`` — the source of truth.
  * ``Asset.qr_token`` — a permanent opaque random token that is the ONLY
    thing encoded in the printed QR. It never contains location or serial
    data and never changes when the asset moves.

The legacy free-text columns (``current_location`` / ``from_location`` /
``to_location``) are kept and written in sync with the FK columns for
backward compatibility and data safety — they are not the source of truth.
"""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class AssetStatus(str, enum.Enum):
    ACTIVE = "active"
    UNDER_MAINTENANCE = "under_maintenance"
    SENT_FOR_SERVICE = "sent_for_service"
    RETIRED = "retired"


class Location(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A hospital venue an asset can live in (OT-1, Andrology Lab, Store Room B…).
    Staff pick from this master list when registering or moving an asset — a
    location is never free text during a normal movement."""
    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    building: Mapped[str | None] = mapped_column(String(128), nullable=True)
    floor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    in_charge: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class Asset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assets"

    asset_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)

    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Source of truth for the current location.
    current_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True, index=True
    )
    # Loaded explicitly by the service (selectinload / refresh); not auto-eager,
    # so an Asset that merely enters a shared session never schedules a load.
    current_location_ref: Mapped["Location | None"] = relationship(
        "Location", foreign_keys=[current_location_id], lazy="raise_on_sql"
    )
    # Legacy denormalised text copy (kept in sync; NOT authoritative).
    current_location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Permanent opaque token, the only payload in the printed QR. Set once at
    # registration, never regenerated on a move.
    qr_token: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)

    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    warranty_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    amc_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), default=AssetStatus.ACTIVE, index=True)

    registered_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class AssetMovement(Base, UUIDPrimaryKeyMixin):
    """Immutable — same DB-grant policy as audit_events and
    cryo_custody_events (spec §20: 'Movement history must be immutable').
    A correction is a new row, never an edit."""
    __tablename__ = "asset_movements"

    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "register", "move"

    from_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True)
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True)
    from_location_ref: Mapped["Location | None"] = relationship("Location", foreign_keys=[from_location_id], lazy="raise_on_sql")
    to_location_ref: Mapped["Location | None"] = relationship("Location", foreign_keys=[to_location_id], lazy="raise_on_sql")

    # Legacy denormalised text copies (kept in sync; NOT authoritative).
    from_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # No ORM relationship to User here on purpose — the history serializer
    # resolves the display name with a single batched id->name query, which
    # avoids configuring the User mapper (and its 'Role' string ref) lazily
    # inside a request.
    performed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

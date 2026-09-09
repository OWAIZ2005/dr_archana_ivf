import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.assets.models import Asset, AssetMovement, AssetStatus, Location
from app.assets.schemas import (
    AssetCreate,
    AssetDetailOut,
    AssetMoveRequest,
    AssetMovementOut,
    AssetOut,
    AssetUpdate,
    LocationCreate,
    LocationOut,
)
from app.audit.service import record_audit_event
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.events.bus import EventType, emit


# --------------------------- serialisation helpers ------------------------- #

def _loc_out(loc: Location | None) -> LocationOut | None:
    return LocationOut.model_validate(loc) if loc is not None else None


def _asset_out(asset: Asset, *, detail: bool = False) -> AssetOut | AssetDetailOut:
    common = dict(
        id=asset.id,
        asset_code=asset.asset_code,
        name=asset.name,
        category=asset.category,
        brand=asset.brand,
        model=asset.model,
        serial_number=asset.serial_number,
        status=asset.status,
        qr_token=asset.qr_token,
        current_location=_loc_out(asset.current_location_ref),
        updated_at=asset.updated_at,
    )
    if not detail:
        return AssetOut(**common)
    return AssetDetailOut(
        **common,
        purchase_date=asset.purchase_date,
        cost_paise=asset.cost_paise,
        warranty_until=asset.warranty_until,
        amc_until=asset.amc_until,
        registered_by_id=asset.registered_by_id,
        created_at=asset.created_at,
    )


def _movement_out(mv: AssetMovement, user_names: dict[uuid.UUID, str] | None = None) -> AssetMovementOut:
    return AssetMovementOut(
        id=mv.id,
        event_type=mv.event_type,
        from_location=_loc_out(mv.from_location_ref),
        to_location=_loc_out(mv.to_location_ref),
        note=mv.notes,
        moved_by_id=mv.performed_by_id,
        moved_by_name=(user_names or {}).get(mv.performed_by_id),
        moved_at=mv.occurred_at,
    )


# -------------------------------- locations ------------------------------- #

async def create_location(
    session: AsyncSession, data: LocationCreate, *, actor_id: uuid.UUID, actor_role: str
) -> LocationOut:
    exists = (
        await session.execute(select(Location.id).where(Location.name == data.name))
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("A location with that name already exists.", error_code="location_exists")

    loc = Location(**data.model_dump())
    session.add(loc)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="assets.location_created", entity_type="Location", entity_id=str(loc.id),
        after_state={"name": loc.name},
    )
    return _loc_out(loc)


async def list_locations(session: AsyncSession, *, active_only: bool = True) -> list[LocationOut]:
    stmt = select(Location).order_by(Location.name)
    if active_only:
        stmt = stmt.where(Location.is_active.is_(True))
    rows = (await session.execute(stmt)).scalars().all()
    return [_loc_out(r) for r in rows]


async def get_location(session: AsyncSession, location_id: uuid.UUID) -> LocationOut:
    loc = await session.get(Location, location_id)
    if loc is None:
        raise NotFoundError("Location not found", error_code="location_not_found")
    return _loc_out(loc)


async def _require_location(session: AsyncSession, location_id: uuid.UUID) -> Location:
    loc = await session.get(Location, location_id)
    if loc is None:
        raise ValidationFailedError("That location does not exist.", error_code="location_not_found")
    if not loc.is_active:
        raise ValidationFailedError("That location is inactive.", error_code="location_inactive")
    return loc


# ---------------------------------- assets -------------------------------- #

async def _next_asset_code(session: AsyncSession) -> str:
    result = await session.execute(
        select(Asset.asset_code).order_by(Asset.created_at.desc()).limit(1).with_for_update()
    )
    last = result.scalar_one_or_none()
    tail = last.split("-")[-1] if last else None
    next_seq = int(tail) + 1 if tail and tail.isdigit() else 1
    return f"AST-{next_seq:06d}"


async def create_asset(
    session: AsyncSession, data: AssetCreate, *, actor_id: uuid.UUID, actor_role: str
) -> AssetDetailOut:
    location = await _require_location(session, data.current_location_id)

    payload = data.model_dump(exclude={"current_location_id"})
    asset = Asset(
        asset_code=await _next_asset_code(session),
        qr_token=secrets.token_urlsafe(24),
        current_location_id=location.id,
        current_location=location.name,  # legacy text copy, kept in sync
        registered_by_id=actor_id,
        **payload,
    )
    asset.current_location_ref = location  # set the loaded object, no extra query
    session.add(asset)
    await session.flush()

    # Initial "Asset registered" journey event (from = nothing).
    session.add(AssetMovement(
        asset_id=asset.id, event_type="register",
        from_location_id=None, to_location_id=location.id,
        from_location=None, to_location=location.name,
        notes=None, performed_by_id=actor_id, occurred_at=datetime.now(timezone.utc),
    ))
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="assets.registered", entity_type="Asset", entity_id=str(asset.id),
        after_state={"asset_code": asset.asset_code, "location": location.name},
    )
    return _asset_out(asset, detail=True)


def _asset_load_opts():
    # Built at call time, never at import — referencing Asset.current_location_ref
    # eagerly would force mapper configuration before app.roles is imported.
    return (selectinload(Asset.current_location_ref),)


async def _one_asset(session: AsyncSession, whereclause) -> Asset | None:
    return (
        await session.execute(select(Asset).options(*_asset_load_opts()).where(whereclause))
    ).scalar_one_or_none()


async def get_asset(session: AsyncSession, asset_id: uuid.UUID) -> AssetDetailOut:
    asset = await _one_asset(session, Asset.id == asset_id)
    if asset is None:
        raise NotFoundError("Asset not found", error_code="asset_not_found")
    return _asset_out(asset, detail=True)


async def get_asset_by_code(session: AsyncSession, asset_code: str) -> AssetDetailOut:
    asset = await _one_asset(session, Asset.asset_code == asset_code)
    if asset is None:
        raise NotFoundError("Asset not found for this code", error_code="asset_not_found")
    return _asset_out(asset, detail=True)


async def resolve_qr(session: AsyncSession, qr_token: str) -> AssetDetailOut:
    """QR-scan entry point. The token is opaque and permanent; the location
    returned is always read from live DB state."""
    if not qr_token or len(qr_token) < 16:
        raise NotFoundError("Invalid QR code", error_code="invalid_qr_token")
    asset = await _one_asset(session, Asset.qr_token == qr_token)
    if asset is None:
        raise NotFoundError("Invalid or unknown QR code", error_code="invalid_qr_token")
    return _asset_out(asset, detail=True)


async def search_assets(
    session: AsyncSession,
    *,
    q: str | None = None,
    location_id: uuid.UUID | None = None,
    category: str | None = None,
    status: AssetStatus | None = None,
    limit: int = 100,
) -> list[AssetOut]:
    stmt = select(Asset).options(*_asset_load_opts()).order_by(Asset.updated_at.desc()).limit(limit)
    if q:
        term = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Asset.name.ilike(term),
                Asset.asset_code.ilike(term),
                Asset.serial_number.ilike(term),
            )
        )
    if location_id is not None:
        stmt = stmt.where(Asset.current_location_id == location_id)
    if category:
        stmt = stmt.where(Asset.category == category)
    if status is not None:
        stmt = stmt.where(Asset.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [_asset_out(r) for r in rows]


async def update_asset(
    session: AsyncSession, asset_id: uuid.UUID, data: AssetUpdate, *, actor_id: uuid.UUID, actor_role: str
) -> AssetDetailOut:
    asset = await _one_asset(session, Asset.id == asset_id)
    if asset is None:
        raise NotFoundError("Asset not found", error_code="asset_not_found")

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return _asset_out(asset, detail=True)
    before = {k: getattr(asset, k) for k in changes}
    for k, v in changes.items():
        setattr(asset, k, v)
    await session.flush()
    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="assets.updated", entity_type="Asset", entity_id=str(asset.id),
        before_state={k: (v.value if hasattr(v, "value") else v) for k, v in before.items()},
        after_state={k: (v.value if hasattr(v, "value") else v) for k, v in changes.items()},
    )
    return _asset_out(asset, detail=True)


async def move_asset(
    session: AsyncSession,
    asset_id: uuid.UUID,
    body: AssetMoveRequest,
    *,
    actor_id: uuid.UUID,
    actor_role: str,
) -> AssetDetailOut:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise NotFoundError("Asset not found", error_code="asset_not_found")

    target = await _require_location(session, body.to_location_id)
    from_id = asset.current_location_id
    from_name = asset.current_location  # legacy text copy — safe, plain column

    # Append-only movement row. Never edits history.
    session.add(AssetMovement(
        asset_id=asset.id, event_type="move",
        from_location_id=from_id, to_location_id=target.id,
        from_location=from_name, to_location=target.name,
        notes=body.note, performed_by_id=actor_id, occurred_at=datetime.now(timezone.utc),
    ))
    # Sync current location (FK + legacy text copy). Do NOT assign the
    # relationship attribute directly — on a persistent row that would lazy-load
    # the previous value; we re-fetch with the relationship eager-loaded below.
    asset.current_location_id = target.id
    asset.current_location = target.name
    await session.flush()

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="assets.moved", entity_type="Asset", entity_id=str(asset.id),
        before_state={"location": from_name}, after_state={"location": target.name},
    )
    await emit(
        session, event_type=EventType.ASSET_MOVED, entity_type="Asset", entity_id=str(asset.id),
        payload={"to_location_id": str(target.id), "to_location": target.name},
    )
    fresh = await _one_asset(session, Asset.id == asset.id)
    return _asset_out(fresh, detail=True)


async def get_movement_history(session: AsyncSession, asset_id: uuid.UUID) -> list[AssetMovementOut]:
    exists = (await session.execute(select(Asset.id).where(Asset.id == asset_id))).scalar_one_or_none()
    if exists is None:
        raise NotFoundError("Asset not found", error_code="asset_not_found")
    rows = (
        await session.execute(
            select(AssetMovement)
            .options(
                selectinload(AssetMovement.from_location_ref),
                selectinload(AssetMovement.to_location_ref),
            )
            .where(AssetMovement.asset_id == asset_id)
            .order_by(AssetMovement.occurred_at, AssetMovement.id)
        )
    ).scalars().all()

    # Batched id -> display name (no ORM relationship to User; see model note).
    user_ids = {r.performed_by_id for r in rows}
    user_names: dict[uuid.UUID, str] = {}
    if user_ids:
        from app.users.models import User

        for uid, name in (
            await session.execute(select(User.id, User.full_name).where(User.id.in_(user_ids)))
        ).all():
            user_names[uid] = name

    return [_movement_out(r, user_names) for r in rows]


async def get_asset_orm(session: AsyncSession, asset_id: uuid.UUID) -> Asset:
    """For the label endpoint, which needs the raw ORM object."""
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise NotFoundError("Asset not found", error_code="asset_not_found")
    return asset

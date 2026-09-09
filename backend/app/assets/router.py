import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets import service
from app.assets.label import render_asset_label_pdf
from app.assets.qr import build_scan_payload
from app.assets.models import AssetStatus
from app.assets.schemas import (
    AssetCreate,
    AssetDetailOut,
    AssetMovementOut,
    AssetMoveRequest,
    AssetOut,
    AssetUpdate,
    LocationCreate,
    LocationOut,
)
from app.audit.service import record_audit_event
from app.core.database import get_db
from app.core.deps import require_permission
from app.printing.service import generate_qr_png, record_print_event
from app.users.models import User

router = APIRouter(prefix="/assets", tags=["assets"])


# --------------------------------- locations ----------------------------- #

@router.post("/locations", response_model=LocationOut, status_code=201)
async def create_location(
    body: LocationCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("assets.register")),
) -> LocationOut:
    return await service.create_location(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/locations", response_model=list[LocationOut])
async def list_locations(
    include_inactive: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("assets.read")),
) -> list[LocationOut]:
    return await service.list_locations(session, active_only=not include_inactive)


@router.get("/locations/{location_id}", response_model=LocationOut)
async def get_location(
    location_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("assets.read")),
) -> LocationOut:
    return await service.get_location(session, location_id)


# ---------------------------------- assets ------------------------------- #

@router.post("", response_model=AssetDetailOut, status_code=201)
async def create_asset(
    body: AssetCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("assets.register")),
) -> AssetDetailOut:
    return await service.create_asset(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("", response_model=list[AssetOut])
async def list_assets(
    q: str | None = Query(default=None),
    location_id: uuid.UUID | None = Query(default=None),
    category: str | None = Query(default=None),
    status: AssetStatus | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("assets.read")),
) -> list[AssetOut]:
    return await service.search_assets(
        session, q=q, location_id=location_id, category=category, status=status
    )


@router.get("/resolve/{qr_token}", response_model=AssetDetailOut)
async def resolve_qr(
    qr_token: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("assets.read")),
) -> AssetDetailOut:
    """QR-scan entry point — opaque token in, live asset+location out.
    Requires authentication; the QR sticker alone grants nothing."""
    return await service.resolve_qr(session, qr_token)


@router.get("/by-code/{asset_code}", response_model=AssetDetailOut)
async def get_by_code(
    asset_code: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("assets.read")),
) -> AssetDetailOut:
    return await service.get_asset_by_code(session, asset_code)


@router.get("/{asset_id}", response_model=AssetDetailOut)
async def get_asset(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("assets.read")),
) -> AssetDetailOut:
    return await service.get_asset(session, asset_id)


@router.patch("/{asset_id}", response_model=AssetDetailOut)
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("assets.register")),
) -> AssetDetailOut:
    return await service.update_asset(session, asset_id, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/{asset_id}/move", response_model=AssetDetailOut)
async def move_asset(
    asset_id: uuid.UUID,
    body: AssetMoveRequest,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("assets.move")),
) -> AssetDetailOut:
    return await service.move_asset(session, asset_id, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/{asset_id}/history", response_model=list[AssetMovementOut])
async def get_history(
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("assets.read")),
) -> list[AssetMovementOut]:
    return await service.get_movement_history(session, asset_id)


@router.get("/{asset_id}/qr")
async def get_qr_png(
    asset_id: uuid.UUID,
    base: str | None = Query(
        default=None,
        description="Application base URL to encode as <base>/#scan=<token>. "
        "Supplied by the frontend from NEXT_PUBLIC_APP_URL; never an IP hardcoded here.",
    ),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("assets.read")),
) -> Response:
    """Raw QR PNG for on-screen preview. Encodes only ``<app-url>/#scan=<token>``
    (or the bare opaque token when no base URL is configured)."""
    asset = await service.get_asset_orm(session, asset_id)
    payload = build_scan_payload(asset.qr_token, base)
    return Response(content=generate_qr_png(payload), media_type="image/png")


@router.get("/{asset_id}/label")
async def get_label(
    asset_id: uuid.UUID,
    base: str | None = Query(
        default=None,
        description="Application base URL to encode as <base>/#scan=<token>. "
        "Supplied by the frontend from NEXT_PUBLIC_APP_URL; never an IP hardcoded here.",
    ),
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("assets.read")),
) -> StreamingResponse:
    """One-per-page printable QR label (clinic name + asset name + code + QR).
    Reuses app/printing: qrcode PNG embedded in an fpdf2 page + a print-event
    log row. The QR encodes ``<app-url>/#scan=<token>`` only."""
    asset = await service.get_asset_orm(session, asset_id)
    pdf_bytes = render_asset_label_pdf(asset, qr_payload=build_scan_payload(asset.qr_token, base))

    await record_print_event(
        session, document_type="asset_label", printed_by_id=current.id,
        context_entity_type="Asset", context_entity_id=str(asset.id),
    )
    await record_audit_event(
        session, actor_id=current.id, actor_role=current.role.code,
        action="assets.label_printed", entity_type="Asset", entity_id=str(asset.id),
    )

    def _iter():
        yield pdf_bytes

    return StreamingResponse(
        _iter(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="asset_{asset.asset_code}.pdf"'},
    )

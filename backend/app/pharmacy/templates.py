"""Medicine Templates — reusable groups of medicines (e.g. "OT Kit"),
Phase 2 of the Pharmacy Management module.

A template references real Medicine rows by FK; it never copies medicine
name/price/stock into itself, so an edit to a medicine (or its price)
is reflected wherever the template is displayed. An indent created "from"
a template snapshots the requested quantities onto its own IndentItem
rows at creation time (already true of app.pharmacy.service.create_indent)
— later template edits never retroactively change an existing indent.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from app.audit.service import record_audit_event
from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base, get_db
from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.users.models import User

# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class TemplateStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class MedicineTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "medicine_templates"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[TemplateStatus] = mapped_column(Enum(TemplateStatus, name="templatestatus"), default=TemplateStatus.ACTIVE, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    items: Mapped[list["TemplateMedicineMapping"]] = relationship(back_populates="template", lazy="selectin", cascade="all, delete-orphan")


class TemplateMedicineMapping(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "template_medicine_mappings"
    __table_args__ = (UniqueConstraint("template_id", "medicine_id", name="uq_template_medicine"),)

    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicine_templates.id"), nullable=False, index=True)
    template: Mapped["MedicineTemplate"] = relationship(back_populates="items")

    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    default_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class TemplateItemIn(BaseModel):
    medicine_id: uuid.UUID
    default_quantity: int = Field(gt=0)
    notes: str | None = None


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    items: list[TemplateItemIn] = []


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: TemplateStatus | None = None


class TemplateItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    medicine_id: uuid.UUID
    default_quantity: int
    notes: str | None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    status: TemplateStatus
    items: list[TemplateItemOut]
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #


async def list_templates(session: AsyncSession, *, status: TemplateStatus | None = None, search: str | None = None) -> list[MedicineTemplate]:
    stmt = select(MedicineTemplate).order_by(MedicineTemplate.name)
    if status is not None:
        stmt = stmt.where(MedicineTemplate.status == status)
    if search:
        stmt = stmt.where(MedicineTemplate.name.ilike(f"%{search}%"))
    return list((await session.execute(stmt)).scalars().all())


async def get_template(session: AsyncSession, template_id: uuid.UUID) -> MedicineTemplate:
    result = await session.execute(
        select(MedicineTemplate).options(selectinload(MedicineTemplate.items)).where(MedicineTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise NotFoundError("Template not found", error_code="template_not_found")
    return template


async def create_template(session: AsyncSession, data: TemplateCreate, *, actor_id: uuid.UUID, actor_role: str) -> MedicineTemplate:
    exists = (await session.execute(select(MedicineTemplate.id).where(MedicineTemplate.name == data.name))).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("A template with that name already exists.", error_code="template_exists")

    template = MedicineTemplate(name=data.name, description=data.description, created_by_id=actor_id)
    session.add(template)
    await session.flush()
    for item in data.items:
        session.add(TemplateMedicineMapping(template_id=template.id, medicine_id=item.medicine_id, default_quantity=item.default_quantity, notes=item.notes))
    await session.flush()
    await session.refresh(template, attribute_names=["items"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.template_created", entity_type="MedicineTemplate", entity_id=str(template.id),
        after_state={"name": template.name, "item_count": len(data.items)},
    )
    return template


async def update_template(session: AsyncSession, template_id: uuid.UUID, data: TemplateUpdate, *, actor_id: uuid.UUID, actor_role: str) -> MedicineTemplate:
    template = await session.get(MedicineTemplate, template_id)
    if not template:
        raise NotFoundError("Template not found", error_code="template_not_found")
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(template, k, v)
    if changes:
        template.updated_by_id = actor_id
    await session.flush()
    await session.refresh(template)

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.template_updated", entity_type="MedicineTemplate", entity_id=str(template.id),
        after_state={k: (v.value if hasattr(v, "value") else v) for k, v in changes.items()},
    )
    return template


async def add_template_item(session: AsyncSession, template_id: uuid.UUID, data: TemplateItemIn, *, actor_id: uuid.UUID, actor_role: str) -> MedicineTemplate:
    template = await session.get(MedicineTemplate, template_id)
    if not template:
        raise NotFoundError("Template not found", error_code="template_not_found")
    exists = (
        await session.execute(
            select(TemplateMedicineMapping.id).where(
                TemplateMedicineMapping.template_id == template_id, TemplateMedicineMapping.medicine_id == data.medicine_id
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("That medicine is already on this template — edit its quantity instead.", error_code="duplicate_template_medicine")

    session.add(TemplateMedicineMapping(template_id=template_id, medicine_id=data.medicine_id, default_quantity=data.default_quantity, notes=data.notes))
    template.updated_by_id = actor_id
    await session.flush()
    await session.refresh(template, attribute_names=["items"])
    # `updated_at` is server-generated (onupdate=func.now()) — the flush
    # above (setting updated_by_id) expires it on this object; refresh
    # before the response is serialized outside the async context.
    await session.refresh(template)
    return template


async def update_template_item(session: AsyncSession, template_id: uuid.UUID, item_id: uuid.UUID, quantity: int, *, actor_id: uuid.UUID) -> MedicineTemplate:
    if quantity <= 0:
        raise ValidationFailedError("Quantity must be greater than zero.")
    item = await session.get(TemplateMedicineMapping, item_id)
    if not item or item.template_id != template_id:
        raise NotFoundError("Template line not found.", error_code="template_item_not_found")
    item.default_quantity = quantity
    template = await session.get(MedicineTemplate, template_id)
    template.updated_by_id = actor_id
    await session.flush()
    await session.refresh(template, attribute_names=["items"])
    await session.refresh(template)
    return template


async def remove_template_item(session: AsyncSession, template_id: uuid.UUID, item_id: uuid.UUID, *, actor_id: uuid.UUID) -> MedicineTemplate:
    item = await session.get(TemplateMedicineMapping, item_id)
    if not item or item.template_id != template_id:
        raise NotFoundError("Template line not found.", error_code="template_item_not_found")
    await session.delete(item)
    template = await session.get(MedicineTemplate, template_id)
    template.updated_by_id = actor_id
    await session.flush()
    await session.refresh(template, attribute_names=["items"])
    await session.refresh(template)
    return template


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #

router = APIRouter(prefix="/pharmacy/templates", tags=["pharmacy-templates"])


@router.get("", response_model=list[TemplateOut])
async def list_templates_endpoint(
    status: TemplateStatus | None = Query(default=None),
    search: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[TemplateOut]:
    return await list_templates(session, status=status, search=search)


@router.post("", response_model=TemplateOut, status_code=201)
async def create_template_endpoint(
    body: TemplateCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> TemplateOut:
    return await create_template(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template_endpoint(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> TemplateOut:
    return await get_template(session, template_id)


@router.patch("/{template_id}", response_model=TemplateOut)
async def update_template_endpoint(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> TemplateOut:
    await update_template(session, template_id, body, actor_id=current.id, actor_role=current.role.code)
    return await get_template(session, template_id)


@router.post("/{template_id}/items", response_model=TemplateOut, status_code=201)
async def add_template_item_endpoint(
    template_id: uuid.UUID,
    body: TemplateItemIn,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> TemplateOut:
    return await add_template_item(session, template_id, body, actor_id=current.id, actor_role=current.role.code)


class TemplateItemQuantityUpdate(BaseModel):
    quantity: int


@router.patch("/{template_id}/items/{item_id}", response_model=TemplateOut)
async def update_template_item_endpoint(
    template_id: uuid.UUID,
    item_id: uuid.UUID,
    body: TemplateItemQuantityUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> TemplateOut:
    return await update_template_item(session, template_id, item_id, body.quantity, actor_id=current.id)


@router.delete("/{template_id}/items/{item_id}", response_model=TemplateOut)
async def remove_template_item_endpoint(
    template_id: uuid.UUID,
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> TemplateOut:
    return await remove_template_item(session, template_id, item_id, actor_id=current.id)

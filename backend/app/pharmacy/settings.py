"""Phase 6 — Pharmacy Settings (a single persisted row: print/invoice
configuration) and Indent Templates (reusable department-request
structures — distinct from MedicineTemplate, a reusable medicine kit).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.audit.service import record_audit_event
from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base, get_db
from app.core.deps import require_permission
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.users.models import User

SETTINGS_SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class PharmacySettings(Base, TimestampMixin):
    __tablename__ = "pharmacy_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=lambda: SETTINGS_SINGLETON_ID)
    pharmacy_name: Mapped[str] = mapped_column(String(255), default="Dr. Archana IVF & Women Centre — Pharmacy")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(16), nullable=True)
    invoice_header: Mapped[str | None] = mapped_column(String(500), nullable=True)
    invoice_footer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    show_gst: Mapped[bool] = mapped_column(Boolean, default=True)
    show_doctor: Mapped[bool] = mapped_column(Boolean, default=True)
    show_patient_details: Mapped[bool] = mapped_column(Boolean, default=True)
    show_batch: Mapped[bool] = mapped_column(Boolean, default=True)
    show_expiry: Mapped[bool] = mapped_column(Boolean, default=True)
    show_mrp: Mapped[bool] = mapped_column(Boolean, default=True)
    show_payment_info: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class IndentTemplateStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class IndentTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "indent_templates"

    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    room: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[IndentTemplateStatus] = mapped_column(Enum(IndentTemplateStatus, name="indenttemplatestatus"), default=IndentTemplateStatus.ACTIVE, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    items: Mapped[list["IndentTemplateItem"]] = relationship(back_populates="template", lazy="selectin", cascade="all, delete-orphan")


class IndentTemplateItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "indent_template_items"

    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("indent_templates.id"), nullable=False, index=True)
    template: Mapped["IndentTemplate"] = relationship(back_populates="items")

    medicine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("medicines.id"), nullable=False)
    default_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class PharmacySettingsUpdate(BaseModel):
    pharmacy_name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    invoice_header: str | None = None
    invoice_footer: str | None = None
    show_gst: bool | None = None
    show_doctor: bool | None = None
    show_patient_details: bool | None = None
    show_batch: bool | None = None
    show_expiry: bool | None = None
    show_mrp: bool | None = None
    show_payment_info: bool | None = None


class PharmacySettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pharmacy_name: str
    address: str | None
    phone: str | None
    email: str | None
    gstin: str | None
    invoice_header: str | None
    invoice_footer: str | None
    show_gst: bool
    show_doctor: bool
    show_patient_details: bool
    show_batch: bool
    show_expiry: bool
    show_mrp: bool
    show_payment_info: bool
    updated_at: datetime


class IndentTemplateItemIn(BaseModel):
    medicine_id: uuid.UUID
    default_quantity: int = Field(gt=0)
    notes: str | None = None


class IndentTemplateCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    department: str | None = None
    room: str | None = None
    items: list[IndentTemplateItemIn] = []


class IndentTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    department: str | None = None
    room: str | None = None
    status: IndentTemplateStatus | None = None
    items: list[IndentTemplateItemIn] | None = None


class IndentTemplateItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    medicine_id: uuid.UUID
    default_quantity: int
    notes: str | None


class IndentTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    department: str | None
    room: str | None
    status: IndentTemplateStatus
    items: list[IndentTemplateItemOut]
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Service — settings
# --------------------------------------------------------------------------- #


async def get_settings(session: AsyncSession) -> PharmacySettings:
    settings = await session.get(PharmacySettings, SETTINGS_SINGLETON_ID)
    if not settings:
        settings = PharmacySettings(id=SETTINGS_SINGLETON_ID)
        session.add(settings)
        await session.flush()
        await session.refresh(settings)
    return settings


async def update_settings(session: AsyncSession, data: PharmacySettingsUpdate, *, actor_id: uuid.UUID, actor_role: str) -> PharmacySettings:
    settings = await get_settings(session)
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(settings, k, v)
    settings.updated_by_id = actor_id
    await session.flush()
    await session.refresh(settings)

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.settings_updated", entity_type="PharmacySettings", entity_id=str(settings.id),
        after_state={k: v for k, v in changes.items()},
    )
    return settings


# --------------------------------------------------------------------------- #
# Service — indent templates
# --------------------------------------------------------------------------- #


async def list_indent_templates(session: AsyncSession, *, status: IndentTemplateStatus | None = None) -> list[IndentTemplate]:
    stmt = select(IndentTemplate).order_by(IndentTemplate.name)
    if status is not None:
        stmt = stmt.where(IndentTemplate.status == status)
    return list((await session.execute(stmt)).scalars().all())


async def get_indent_template(session: AsyncSession, template_id: uuid.UUID) -> IndentTemplate:
    t = await session.get(IndentTemplate, template_id)
    if not t:
        raise NotFoundError("Indent template not found", error_code="indent_template_not_found")
    return t


async def create_indent_template(session: AsyncSession, data: IndentTemplateCreate, *, actor_id: uuid.UUID, actor_role: str) -> IndentTemplate:
    template = IndentTemplate(name=data.name, description=data.description, department=data.department, room=data.room, created_by_id=actor_id)
    session.add(template)
    await session.flush()
    for item in data.items:
        session.add(IndentTemplateItem(template_id=template.id, medicine_id=item.medicine_id, default_quantity=item.default_quantity, notes=item.notes))
    await session.flush()
    await session.refresh(template, attribute_names=["items"])

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.indent_template_created", entity_type="IndentTemplate", entity_id=str(template.id),
        after_state={"name": template.name},
    )
    return template


async def update_indent_template(session: AsyncSession, template_id: uuid.UUID, data: IndentTemplateUpdate, *, actor_id: uuid.UUID, actor_role: str) -> IndentTemplate:
    template = await get_indent_template(session, template_id)
    changes = data.model_dump(exclude_unset=True, exclude={"items"})
    for k, v in changes.items():
        setattr(template, k, v)
    if data.items is not None:
        for existing in list(template.items):
            await session.delete(existing)
        await session.flush()
        for item in data.items:
            session.add(IndentTemplateItem(template_id=template.id, medicine_id=item.medicine_id, default_quantity=item.default_quantity, notes=item.notes))
    await session.flush()
    await session.refresh(template, attribute_names=["items"])
    await session.refresh(template)

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="pharmacy.indent_template_updated", entity_type="IndentTemplate", entity_id=str(template.id),
        after_state={k: (v.value if hasattr(v, "value") else v) for k, v in changes.items()},
    )
    return template


async def duplicate_indent_template(session: AsyncSession, template_id: uuid.UUID, *, actor_id: uuid.UUID, actor_role: str) -> IndentTemplate:
    original = await get_indent_template(session, template_id)
    copy = IndentTemplate(
        name=f"{original.name} (Copy)", description=original.description, department=original.department,
        room=original.room, created_by_id=actor_id,
    )
    session.add(copy)
    await session.flush()
    for item in original.items:
        session.add(IndentTemplateItem(template_id=copy.id, medicine_id=item.medicine_id, default_quantity=item.default_quantity, notes=item.notes))
    await session.flush()
    await session.refresh(copy, attribute_names=["items"])
    return copy


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #

router = APIRouter(prefix="/pharmacy", tags=["pharmacy-settings"])


@router.get("/settings", response_model=PharmacySettingsOut)
async def get_settings_endpoint(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> PharmacySettingsOut:
    return await get_settings(session)


@router.put("/settings", response_model=PharmacySettingsOut)
async def update_settings_endpoint(
    body: PharmacySettingsUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.settings_manage")),
) -> PharmacySettingsOut:
    return await update_settings(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/indent-templates", response_model=list[IndentTemplateOut])
async def list_indent_templates_endpoint(
    status: IndentTemplateStatus | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> list[IndentTemplateOut]:
    return await list_indent_templates(session, status=status)


@router.post("/indent-templates", response_model=IndentTemplateOut, status_code=201)
async def create_indent_template_endpoint(
    body: IndentTemplateCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> IndentTemplateOut:
    return await create_indent_template(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/indent-templates/{template_id}", response_model=IndentTemplateOut)
async def get_indent_template_endpoint(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pharmacy.read")),
) -> IndentTemplateOut:
    return await get_indent_template(session, template_id)


@router.patch("/indent-templates/{template_id}", response_model=IndentTemplateOut)
async def update_indent_template_endpoint(
    template_id: uuid.UUID,
    body: IndentTemplateUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> IndentTemplateOut:
    return await update_indent_template(session, template_id, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/indent-templates/{template_id}/duplicate", response_model=IndentTemplateOut, status_code=201)
async def duplicate_indent_template_endpoint(
    template_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("pharmacy.manage")),
) -> IndentTemplateOut:
    return await duplicate_indent_template(session, template_id, actor_id=current.id, actor_role=current.role.code)

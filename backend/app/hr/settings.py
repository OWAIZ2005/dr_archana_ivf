"""HR-configurable thresholds — attendance full/half-day hours, payroll
rules, and patient-process delay thresholds. One persisted singleton row,
mirroring app/pharmacy/settings.py's pattern exactly (fixed UUID PK,
get-or-create, PUT with audit trail) rather than a generic settings table
— no generic Settings model exists anywhere in this codebase; every
module that needs configurable values keeps its own settings row."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.audit.service import record_audit_event
from app.core.base_model import TimestampMixin
from app.core.database import Base, get_db
from app.core.deps import require_permission
from app.users.models import User

SETTINGS_SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class HrSettings(Base, TimestampMixin):
    __tablename__ = "hr_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=lambda: SETTINGS_SINGLETON_ID)

    # Attendance thresholds (spec §5) — hours, as decimals (e.g. 7.5).
    full_day_hours: Mapped[float] = mapped_column(Numeric(4, 2), default=8.00)
    half_day_min_hours: Mapped[float] = mapped_column(Numeric(4, 2), default=4.00)
    late_arrival_grace_minutes: Mapped[int] = mapped_column(Integer, default=15)
    early_departure_grace_minutes: Mapped[int] = mapped_column(Integer, default=15)
    # The workday's nominal start/end, used only to flag "late arrival" /
    # "early departure" anomalies against entry_time/exit_time — not
    # itself an attendance-status input (that's full/half-day hours above).
    standard_start_time: Mapped[str] = mapped_column(String(5), default="09:00")  # "HH:MM"
    standard_end_time: Mapped[str] = mapped_column(String(5), default="17:00")

    # Payroll rules (spec §8/§25).
    working_days_per_month: Mapped[int] = mapped_column(Integer, default=26)
    half_day_pay_fraction: Mapped[float] = mapped_column(Numeric(3, 2), default=0.50)  # fraction of a full day's pay a half-day earns
    absent_day_pay_fraction: Mapped[float] = mapped_column(Numeric(3, 2), default=0.00)  # fraction of a full day's pay an absent day earns — 0 = no pay
    overtime_rate_per_hour_rupees: Mapped[int] = mapped_column(Integer, default=0)  # 0 = overtime not paid, just shown

    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class HrSettingsUpdate(BaseModel):
    full_day_hours: float | None = None
    half_day_min_hours: float | None = None
    late_arrival_grace_minutes: int | None = None
    early_departure_grace_minutes: int | None = None
    standard_start_time: str | None = None
    standard_end_time: str | None = None
    working_days_per_month: int | None = None
    half_day_pay_fraction: float | None = None
    absent_day_pay_fraction: float | None = Field(default=None, ge=0, le=1)
    overtime_rate_per_hour_rupees: int | None = None


class HrSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    full_day_hours: float
    half_day_min_hours: float
    late_arrival_grace_minutes: int
    early_departure_grace_minutes: int
    standard_start_time: str
    standard_end_time: str
    working_days_per_month: int
    half_day_pay_fraction: float
    absent_day_pay_fraction: float
    overtime_rate_per_hour_rupees: int
    updated_at: datetime


async def get_settings(session: AsyncSession) -> HrSettings:
    settings = await session.get(HrSettings, SETTINGS_SINGLETON_ID)
    if not settings:
        settings = HrSettings(id=SETTINGS_SINGLETON_ID)
        session.add(settings)
        await session.flush()
        await session.refresh(settings)
    return settings


async def update_settings(session: AsyncSession, data: HrSettingsUpdate, *, actor_id: uuid.UUID, actor_role: str) -> HrSettings:
    settings = await get_settings(session)
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(settings, k, v)
    settings.updated_by_id = actor_id
    await session.flush()
    await session.refresh(settings)

    await record_audit_event(
        session, actor_id=actor_id, actor_role=actor_role,
        action="hr.settings_updated", entity_type="HrSettings", entity_id=str(settings.id),
        after_state=changes,
    )
    return settings


router = APIRouter(prefix="/hr", tags=["hr-settings"])


@router.get("/settings", response_model=HrSettingsOut)
async def get_settings_endpoint(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.read")),
) -> HrSettingsOut:
    return await get_settings(session)


@router.put("/settings", response_model=HrSettingsOut)
async def update_settings_endpoint(
    body: HrSettingsUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.settings_manage")),
) -> HrSettingsOut:
    return await update_settings(session, body, actor_id=current.id, actor_role=current.role.code)

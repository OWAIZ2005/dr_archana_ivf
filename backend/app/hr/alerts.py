"""HR alerts (spec §18) — aggregated live from real state (attendance
issues, unresolved unknown-biometric-ID import rows, critical patient
delays) rather than a table HR alerts get written into and can go stale
in. The one thing persisted is which alerts a human has already
dismissed (`HrAlertResolution`, keyed by a stable string built from the
alert's own source row), so a dismissed alert stays dismissed across
reloads without the alert itself needing to be a durable row."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import String, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base, get_db
from app.core.deps import require_permission
from app.hr.models import AttendanceImport, AttendanceImportStatus, AttendanceRecord
from app.hr.process import get_delays
from app.users.models import User


class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"


class HrAlertResolution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "hr_alert_resolutions"

    alert_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    resolved_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class HrAlertOut(BaseModel):
    key: str
    severity: AlertSeverity
    category: str
    title: str
    body: str


async def _resolved_keys(session: AsyncSession) -> set[str]:
    rows = (await session.execute(select(HrAlertResolution.alert_key))).scalars().all()
    return set(rows)


async def list_alerts(session: AsyncSession) -> list[HrAlertOut]:
    resolved = await _resolved_keys(session)
    alerts: list[HrAlertOut] = []

    # Critical patient delays
    delays = await get_delays(session, today=datetime.now(timezone.utc).date(), only_delayed=True)
    for d in delays:
        if d.severity != "critical":
            continue
        key = f"delay:{d.appointment_id}:{d.stage}"
        if key in resolved:
            continue
        alerts.append(HrAlertOut(
            key=key, severity=AlertSeverity.CRITICAL, category="patient_delay",
            title="Critical Patient Delay",
            body=f"{d.patient_name} has exceeded the {d.stage.replace('_', ' ')} threshold by {d.delay_minutes} minutes.",
        ))

    # Missing exit/entry attendance issues
    issue_rows = (await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.resolved_at.is_(None),
            (AttendanceRecord.missing_entry.is_(True)) | (AttendanceRecord.missing_exit.is_(True)),
        )
    )).scalars().all()
    for r in issue_rows:
        key = f"attendance_issue:{r.id}"
        if key in resolved:
            continue
        what = "no exit biometric record" if r.missing_exit else "no entry biometric record"
        alerts.append(HrAlertOut(
            key=key, severity=AlertSeverity.WARNING, category="attendance_issue",
            title="Attendance Issue", body=f"Employee record for {r.attendance_date} has {what}.",
        ))

    # Unknown biometric IDs from the most recent unconfirmed imports
    pending_imports = (await session.execute(
        select(AttendanceImport).where(AttendanceImport.status == AttendanceImportStatus.PREVIEWED, AttendanceImport.unknown_count > 0)
    )).scalars().all()
    for imp in pending_imports:
        key = f"unknown_import:{imp.id}"
        if key in resolved:
            continue
        alerts.append(HrAlertOut(
            key=key, severity=AlertSeverity.WARNING, category="attendance_anomaly",
            title="Attendance Anomaly",
            body=f"{imp.unknown_count} unknown biometric ID(s) in '{imp.filename}' — awaiting review before import can be confirmed.",
        ))

    return alerts


async def resolve_alert(session: AsyncSession, key: str, *, actor_id: uuid.UUID, note: str | None = None) -> None:
    existing = (await session.execute(select(HrAlertResolution).where(HrAlertResolution.alert_key == key))).scalar_one_or_none()
    if existing:
        return
    session.add(HrAlertResolution(alert_key=key, resolved_by_id=actor_id, note=note))
    await session.flush()


class ResolveAlertRequest(BaseModel):
    note: str | None = None


router = APIRouter(prefix="/hr/alerts", tags=["hr-alerts"])


@router.get("", response_model=list[HrAlertOut])
async def list_alerts_endpoint(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("hr.read")),
) -> list[HrAlertOut]:
    return await list_alerts(session)


@router.post("/{key:path}/resolve")
async def resolve_alert_endpoint(
    key: str,
    body: ResolveAlertRequest,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("hr.write")),
) -> dict:
    await resolve_alert(session, key, actor_id=current.id, note=body.note)
    return {"resolved": True}

"""The ``report_jobs`` table - one row per asynchronous report-generation
request.

This is separate from the synchronous analytics endpoints in
``app.reports.service`` (dashboard metrics, revenue trend, discharge summary),
which read live and return immediately. A ``ReportJob`` models work that is
handed to a Celery worker: the request returns a job id, the worker generates
the artifact in the background, and the row is the single source of truth for
the lifecycle (``queued -> running -> succeeded | failed``) plus the timings
used to prove jobs run concurrently in the worker rather than serially.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class ReportType(str, enum.Enum):
    patient_summary = "patient_summary"
    discharge_summary = "discharge_summary"


class ReportStatus(str, enum.Enum):
    queued = "queued"        # accepted, waiting for a worker
    running = "running"      # a worker has picked it up
    succeeded = "succeeded"  # artifact stored, ready to download
    failed = "failed"        # generation raised; `error` explains why


class ReportJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "report_jobs"

    # Overrides TimestampMixin's server_default=func.now(): the job list is
    # keyset-paged on (created_at, id), and a server-side now() returns the
    # transaction start time - identical for two jobs queued in one request -
    # which would leave "newest first" undefined. A statement-time Python
    # default has microsecond resolution and orders reliably.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_job_type"), nullable=False
    )
    # Validated request parameters, e.g. {"patient_id": "<uuid>"}.
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Non-domain knobs, e.g. {"simulate_work_seconds": 3}. Never affects output.
    options: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_job_status"),
        nullable=False,
        default=ReportStatus.queued,
    )

    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Set once the job succeeds.
    storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Set once the job fails. Never contains a traceback.
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_report_jobs_created_at_id", text("created_at DESC"), text("id DESC")),
        Index("ix_report_jobs_status", "status"),
    )

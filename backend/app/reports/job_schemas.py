"""Request/response shapes for asynchronous report-generation jobs.

Responses are explicit; ORM objects are never returned directly.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.types import UtcDatetime
from app.reports.job_models import ReportStatus, ReportType

# Every report type shipped so far is scoped to a single patient and takes
# ``parameters.patient_id``.
PATIENT_SCOPED_REPORTS = frozenset(
    {ReportType.patient_summary, ReportType.discharge_summary}
)


class ReportOptions(BaseModel):
    """Non-domain knobs. Never changes the report's content."""

    model_config = ConfigDict(extra="forbid")

    # Makes the worker sleep this many seconds while generating, to model a
    # heavy report and exercise the async pipeline under concurrent load.
    # Bounded server-side by REPORT_SIMULATE_MAX_SECONDS.
    simulate_work_seconds: float = Field(default=0.0, ge=0.0)


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_type: ReportType
    parameters: dict = Field(default_factory=dict)
    options: ReportOptions = Field(default_factory=ReportOptions)

    @model_validator(mode="after")
    def _require_patient_id(self) -> "ReportRequest":
        if self.report_type in PATIENT_SCOPED_REPORTS:
            patient_id = self.parameters.get("patient_id")
            if not patient_id:
                raise ValueError(
                    f"parameters.patient_id is required for a {self.report_type.value} report."
                )
            try:
                UUID(str(patient_id))
            except (ValueError, TypeError):
                raise ValueError("parameters.patient_id must be a valid UUID.") from None
        return self


class ReportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    report_type: ReportType
    parameters: dict
    status: ReportStatus
    requested_by_id: UUID
    error: str | None
    content_type: str | None
    byte_size: int | None
    queued_at: UtcDatetime
    started_at: UtcDatetime | None
    finished_at: UtcDatetime | None
    created_at: UtcDatetime

    @property
    def result_available(self) -> bool:
        return self.status is ReportStatus.succeeded


class ReportJobPage(BaseModel):
    items: list[ReportJobRead]
    next_cursor: str | None = None
    has_more: bool = False

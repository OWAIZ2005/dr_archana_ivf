"""Database access and orchestration for asynchronous report jobs.

``create_report_job`` runs in the request. ``run_report_job`` runs in the Celery
worker: it builds its own async engine/session (safe under the prefork pool),
does the work, and records the outcome and timings on the ``report_jobs`` row.
It never raises to the worker - every failure is captured as ``status="failed"``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.pagination import paginate
from app.patients.models import Patient
from app.reports.job_generators import REPORT_GENERATORS, ReportGenerationError
from app.reports.job_models import ReportJob, ReportStatus, ReportType
from app.reports.job_schemas import PATIENT_SCOPED_REPORTS, ReportRequest
from app.reports.job_storage import ReportArtifactStorage, build_report_storage

_SUFFIX_BY_TYPE = {"application/json": ".json", "text/csv": ".csv", "application/pdf": ".pdf"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _patient_exists(session: AsyncSession, patient_id: UUID) -> bool:
    return (
        await session.execute(sa.select(Patient.id).where(Patient.id == patient_id))
    ).scalar_one_or_none() is not None


async def create_report_job(
    session: AsyncSession,
    request: ReportRequest,
    *,
    requested_by_id: UUID,
    settings: Settings | None = None,
    celery_task_id: str | None = None,
    commit: bool = True,
) -> ReportJob:
    """Validate the request and persist a queued job (one database round trip).

    The caller (the router) chooses the Celery task id up front and passes it in,
    then enqueues *after* this commits - so a worker can never race ahead of the
    row it needs.
    """
    settings = settings or get_settings()

    if request.report_type in PATIENT_SCOPED_REPORTS:
        patient_id = UUID(str(request.parameters["patient_id"]))
        if not await _patient_exists(session, patient_id):
            raise ValidationFailedError(
                "That patient does not exist. Choose a registered patient."
            )
        parameters = {"patient_id": str(patient_id)}
    else:  # pragma: no cover - every report type today is patient-scoped
        parameters = dict(request.parameters)

    simulate = min(
        float(request.options.simulate_work_seconds),
        float(settings.REPORT_SIMULATE_MAX_SECONDS),
    )

    job = ReportJob(
        report_type=request.report_type,
        parameters=parameters,
        options={"simulate_work_seconds": simulate} if simulate else {},
        status=ReportStatus.queued,
        requested_by_id=requested_by_id,
        celery_task_id=celery_task_id,
        queued_at=_utcnow(),
    )
    session.add(job)
    if commit:
        await session.commit()
        await session.refresh(job)
    else:
        await session.flush()
    return job


async def get_report_job(session: AsyncSession, job_id: UUID) -> ReportJob | None:
    return (
        await session.execute(sa.select(ReportJob).where(ReportJob.id == job_id))
    ).scalar_one_or_none()


async def list_report_jobs(
    session: AsyncSession,
    *,
    limit: int,
    cursor: str | None = None,
    status: ReportStatus | None = None,
    report_type: ReportType | None = None,
) -> tuple[list[ReportJob], str | None, bool]:
    stmt = sa.select(ReportJob)
    if status is not None:
        stmt = stmt.where(ReportJob.status == status)
    if report_type is not None:
        stmt = stmt.where(ReportJob.report_type == report_type)
    return await paginate(session, stmt, model=ReportJob, cursor=cursor, limit=limit)


async def get_report_artifact(
    session: AsyncSession, storage: ReportArtifactStorage, job_id: UUID
) -> tuple[ReportJob, bytes] | None:
    job = await get_report_job(session, job_id)
    if job is None:
        return None
    if job.status is not ReportStatus.succeeded or not job.storage_key:
        raise ConflictError(f"The report is not ready (status: {job.status.value}).")
    try:
        with storage.open(job.storage_key) as fh:
            return job, fh.read()
    except FileNotFoundError:
        raise NotFoundError("The generated report artifact is missing.") from None


# --------------------------------------------------------------------------- #
# Worker side
# --------------------------------------------------------------------------- #

async def run_report_job(
    job_id: UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    storage: ReportArtifactStorage | None = None,
) -> ReportStatus:
    """Generate the report for ``job_id`` and record the outcome.

    In the real worker ``session_factory`` and ``storage`` are ``None`` and are
    built here from settings. Tests pass their own so the work hits the test
    database. Returns the terminal status; never raises for a generation error.
    """
    settings = get_settings()
    own_engine = None
    if session_factory is None:
        own_engine = create_async_engine(
            settings.DATABASE_URL, poolclass=NullPool, future=True
        )
        session_factory = async_sessionmaker(
            bind=own_engine, expire_on_commit=False, autoflush=False
        )
    if storage is None:
        storage = build_report_storage(settings)

    try:
        async with session_factory() as session:
            job = await get_report_job(session, job_id)
            if job is None:
                return ReportStatus.failed
            if job.status in (ReportStatus.succeeded, ReportStatus.failed):
                return job.status  # already terminal - do not redo work

            job.status = ReportStatus.running
            job.started_at = _utcnow()
            job.error = None
            await session.commit()

            terminal: ReportStatus
            try:
                simulate = float(job.options.get("simulate_work_seconds", 0) or 0)
                if simulate > 0:
                    await asyncio.sleep(simulate)

                generator = REPORT_GENERATORS.get(job.report_type)
                if generator is None:  # pragma: no cover
                    raise ReportGenerationError(
                        f"No generator for report type {job.report_type.value}."
                    )
                payload, content_type = await generator(session, job.parameters)
                key = storage.put(payload, suffix=_SUFFIX_BY_TYPE.get(content_type, ""))

                job.storage_key = key
                job.content_type = content_type
                job.byte_size = len(payload)
                job.status = ReportStatus.succeeded
                job.finished_at = _utcnow()
                terminal = ReportStatus.succeeded

                # In-app notification for the requester (spec §10). This is an
                # internal bell notification only — no SMS/WhatsApp is sent or
                # implied, since no external patient channel is configured.
                try:
                    from app.notifications.models import NotificationTone
                    from app.notifications.service import push_notification

                    await push_notification(
                        session,
                        user_id=job.requested_by_id,
                        title="Report ready",
                        body=f"Your {job.report_type.value.replace('_', ' ')} is ready to download.",
                        tone=NotificationTone.INFO,
                    )
                except Exception:  # noqa: BLE001 - never fail a finished job on the notify
                    pass
            except ReportGenerationError as exc:
                job.status = ReportStatus.failed
                job.error = str(exc)[:1000]
                job.finished_at = _utcnow()
                terminal = ReportStatus.failed
            except Exception as exc:  # noqa: BLE001 - worker must not die on a bad job
                job.status = ReportStatus.failed
                job.error = f"Report generation failed: {type(exc).__name__}."
                job.finished_at = _utcnow()
                terminal = ReportStatus.failed

            await session.commit()
            return terminal
    finally:
        if own_engine is not None:
            await own_engine.dispose()

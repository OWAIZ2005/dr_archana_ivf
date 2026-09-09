"""API + worker tests for asynchronous report-generation jobs.

The endpoint's job is to validate and enqueue; the worker's job
(``run_report_job``) is driven directly here against the test database, exactly
as the Celery task does in production. End-to-end through a real broker/worker
under concurrent load is covered by ``test_report_jobs_concurrency.py`` (opt-in).
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import hash_password
from app.reports.job_models import ReportJob, ReportStatus
from app.reports.job_storage import InMemoryReportStorage
from app.roles.models import Role
from app.users.models import User

BASE = "/api/v1/reports/jobs"
UNKNOWN = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def report_storage() -> InMemoryReportStorage:
    return InMemoryReportStorage()


@pytest.fixture(autouse=True)
def _override_report_storage(report_storage: InMemoryReportStorage):
    """Point the download endpoint at the same in-memory artifact store the
    `run_job` fixture writes to (the real dependency is a local-FS store)."""
    from app.main import app
    from app.reports.job_storage import get_report_storage

    app.dependency_overrides[get_report_storage] = lambda: report_storage
    yield
    app.dependency_overrides.pop(get_report_storage, None)


@pytest.fixture
def enqueued_jobs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Records job ids handed to Celery without executing the task."""
    submitted: list[str] = []

    def _fake_apply_async(args=None, task_id=None, **_kw):
        submitted.append(args[0])

        class _R:
            id = task_id

        return _R()

    monkeypatch.setattr(
        "app.reports.router.generate_report_task.apply_async", _fake_apply_async
    )
    return submitted


@pytest.fixture
def run_job(db_session: AsyncSession, report_storage: InMemoryReportStorage):
    """Runs a queued job the way the Celery worker would: against the test
    connection (savepoint-nested, rolled back with the test) and an in-memory
    artifact store."""
    from app.reports.job_service import run_report_job

    factory = async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )

    async def _run(job_id: UUID) -> ReportStatus:
        return await run_report_job(job_id, session_factory=factory, storage=report_storage)

    return _run


@pytest.fixture
async def reader_headers(client: AsyncClient, db_session: AsyncSession, seeded_roles) -> dict:
    """A signed-in user with reports.read but NOT reports.generate.

    The it_administrator role is exactly that (audit.read + reports.read, no
    generate) after this feature's roles/seed.py change.
    """
    role = (
        await db_session.execute(select(Role).where(Role.code == "it_administrator"))
    ).scalar_one()
    user = User(
        employee_code="TEST-ITA-001", full_name="IT Admin", email="itadmin@example.com",
        role_id=role.id, password_hash=hash_password("TestPass123!"),
    )
    db_session.add(user)
    await db_session.commit()
    r = await client.post(
        "/api/v1/auth/login", json={"email": "itadmin@example.com", "password": "TestPass123!"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _submit(
    client: AsyncClient,
    headers: dict,
    patient_id: str,
    *,
    report_type: str = "patient_summary",
    **opts,
) -> dict:
    body = {"report_type": report_type, "parameters": {"patient_id": patient_id}}
    if opts:
        body["options"] = opts
    r = await client.post(BASE, json=body, headers=headers)
    assert r.status_code == 202, r.text
    return r.json()


class TestSubmit:
    async def test_accepts_and_queues(self, client, admin_headers, sample_patient, enqueued_jobs):
        body = await _submit(client, admin_headers, str(sample_patient.id))
        assert body["status"] == "queued"
        assert body["report_type"] == "patient_summary"
        assert body["parameters"] == {"patient_id": str(sample_patient.id)}
        assert body["started_at"] is None and body["finished_at"] is None
        assert enqueued_jobs == [body["id"]]

    async def test_requires_generate_permission(self, client, reader_headers, sample_patient):
        r = await client.post(
            BASE,
            json={"report_type": "patient_summary", "parameters": {"patient_id": str(sample_patient.id)}},
            headers=reader_headers,
        )
        assert r.status_code == 403

    async def test_requires_authentication(self, client, sample_patient):
        r = await client.post(
            BASE,
            json={"report_type": "patient_summary", "parameters": {"patient_id": str(sample_patient.id)}},
        )
        assert r.status_code == 401

    async def test_rejects_missing_and_bad_patient_id(self, client, admin_headers):
        assert (
            await client.post(BASE, json={"report_type": "patient_summary", "parameters": {}}, headers=admin_headers)
        ).status_code == 422
        assert (
            await client.post(
                BASE,
                json={"report_type": "patient_summary", "parameters": {"patient_id": "nope"}},
                headers=admin_headers,
            )
        ).status_code == 422

    async def test_rejects_unknown_patient_and_queues_nothing(self, client, admin_headers, enqueued_jobs):
        r = await client.post(
            BASE,
            json={"report_type": "patient_summary", "parameters": {"patient_id": UNKNOWN}},
            headers=admin_headers,
        )
        assert r.status_code == 422
        assert enqueued_jobs == []

    async def test_clamps_simulate_seconds(self, client, admin_headers, sample_patient, db_session):
        body = await _submit(client, admin_headers, str(sample_patient.id), simulate_work_seconds=999)
        job = (
            await db_session.execute(select(ReportJob).where(ReportJob.id == UUID(body["id"])))
        ).scalar_one()
        assert job.options["simulate_work_seconds"] == 30  # REPORT_SIMULATE_MAX_SECONDS

    async def test_discharge_summary_accepts_and_validates_patient(
        self, client, admin_headers, sample_patient, enqueued_jobs
    ):
        body = await _submit(
            client, admin_headers, str(sample_patient.id), report_type="discharge_summary"
        )
        assert body["status"] == "queued"
        assert body["report_type"] == "discharge_summary"
        assert enqueued_jobs == [body["id"]]

        # same guards as patient_summary: patient_id is required and must exist
        assert (
            await client.post(
                BASE,
                json={"report_type": "discharge_summary", "parameters": {}},
                headers=admin_headers,
            )
        ).status_code == 422
        assert (
            await client.post(
                BASE,
                json={"report_type": "discharge_summary", "parameters": {"patient_id": UNKNOWN}},
                headers=admin_headers,
            )
        ).status_code == 422


class TestWorker:
    async def test_generates_a_correct_artifact(
        self, client, admin_headers, sample_patient, enqueued_jobs, run_job
    ):
        submitted = await _submit(client, admin_headers, str(sample_patient.id))

        terminal = await run_job(UUID(submitted["id"]))
        assert terminal is ReportStatus.succeeded

        detail = (await client.get(f"{BASE}/{submitted['id']}", headers=admin_headers)).json()
        assert detail["status"] == "succeeded"
        assert detail["content_type"] == "application/pdf"
        assert detail["byte_size"] > 0
        assert detail["started_at"] and detail["finished_at"]
        assert detail["error"] is None

        result = await client.get(f"{BASE}/{submitted['id']}/result", headers=admin_headers)
        assert result.status_code == 200
        assert result.headers["content-type"] == "application/pdf"
        assert result.headers["content-disposition"].endswith(
            f'patient-summary-{submitted["id"]}.pdf"'
        )
        # a real, openable PDF
        assert result.content.startswith(b"%PDF-")
        assert result.content.rstrip().endswith(b"%%EOF")
        assert len(result.content) > 800

        # the same data the JSON report carried is present in the document text
        from pypdf import PdfReader
        from io import BytesIO

        text = "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(result.content)).pages)
        assert sample_patient.uhid in text
        assert sample_patient.full_name in text
        assert "Patient Summary Report" in text
        assert "Appointments" in text and "Laboratory" in text

    async def test_generates_a_discharge_summary_pdf(
        self, client, admin_headers, sample_patient, enqueued_jobs, run_job
    ):
        submitted = await _submit(
            client, admin_headers, str(sample_patient.id), report_type="discharge_summary"
        )

        terminal = await run_job(UUID(submitted["id"]))
        assert terminal is ReportStatus.succeeded

        detail = (await client.get(f"{BASE}/{submitted['id']}", headers=admin_headers)).json()
        assert detail["status"] == "succeeded"
        assert detail["content_type"] == "application/pdf"
        assert detail["error"] is None

        result = await client.get(f"{BASE}/{submitted['id']}/result", headers=admin_headers)
        assert result.status_code == 200
        assert result.headers["content-type"] == "application/pdf"
        assert result.headers["content-disposition"].endswith(
            f'discharge-summary-{submitted["id"]}.pdf"'
        )
        assert result.content.startswith(b"%PDF-")
        assert result.content.rstrip().endswith(b"%%EOF")

        from io import BytesIO

        from pypdf import PdfReader

        text = "\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(result.content)).pages)
        assert sample_patient.uhid in text
        assert sample_patient.full_name in text
        assert "Discharge Summary" in text
        assert "Diagnosis & Treatment" in text
        assert "Follow-up & Next Visit" in text

    async def test_result_is_409_until_ready(self, client, admin_headers, sample_patient, enqueued_jobs):
        submitted = await _submit(client, admin_headers, str(sample_patient.id))
        r = await client.get(f"{BASE}/{submitted['id']}/result", headers=admin_headers)
        assert r.status_code == 409
        assert r.json()["error_code"] == "conflict"

    async def test_failure_is_captured_not_raised(
        self, client, admin_headers, sample_patient, enqueued_jobs, run_job, db_session
    ):
        submitted = await _submit(client, admin_headers, str(sample_patient.id))

        from app.patients.models import Patient
        from sqlalchemy import delete

        await db_session.execute(delete(Patient).where(Patient.id == sample_patient.id))
        await db_session.commit()

        terminal = await run_job(UUID(submitted["id"]))
        assert terminal is ReportStatus.failed

        detail = (await client.get(f"{BASE}/{submitted['id']}", headers=admin_headers)).json()
        assert detail["status"] == "failed"
        assert detail["error"] == "The patient no longer exists."
        assert (
            await client.get(f"{BASE}/{submitted['id']}/result", headers=admin_headers)
        ).status_code == 409


class TestConcurrency:
    """Proves report jobs run *concurrently*, not one-at-a-time.

    Uses its OWN NullPool engine on the test database (real connections, real
    commits, cleaned up in a finally) because genuine concurrency needs N
    independent connections - the shared savepoint-nested test connection can
    only carry one transaction. Runs N `run_report_job` coroutines with
    `asyncio.gather`, each sleeping `simulate_work_seconds`. Serial execution
    would take ~N*sleep; concurrent takes ~sleep and the
    [started_at, finished_at] windows overlap.
    """

    async def test_jobs_execute_concurrently(self, report_storage):
        import asyncio
        import time
        from datetime import datetime, timezone

        from sqlalchemy import delete
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.core.config import get_settings
        from app.patients.models import Patient
        from app.reports.job_service import run_report_job

        from app.core.security import hash_password
        from app.roles.models import Role
        from app.roles.seed import seed_roles_and_permissions
        from app.users.models import User

        n = 5
        sleep_s = 1.0
        engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool, future=True)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        patient_id = None
        user_id = None
        job_ids: list[UUID] = []
        try:
            async with Session() as s:
                await seed_roles_and_permissions(s)
                await s.commit()
                role_id = (
                    await s.execute(select(Role.id).where(Role.code == "administrator"))
                ).scalar_one()
                user = User(
                    employee_code=f"CONC-{uuid4().hex[:8]}", full_name="Conc User",
                    email=f"conc-{uuid4().hex[:8]}@example.com", role_id=role_id,
                    password_hash=hash_password("TestPass123!"),
                )
                patient = Patient(uhid=f"CONC-{uuid4().hex[:8]}", full_name="Conc Patient", gender="female")
                s.add_all([user, patient])
                await s.flush()
                user_id, patient_id = user.id, patient.id
                jobs = [
                    ReportJob(
                        report_type="patient_summary",
                        parameters={"patient_id": str(patient_id)},
                        options={"simulate_work_seconds": sleep_s},
                        status=ReportStatus.queued,
                        requested_by_id=user_id,
                        queued_at=datetime.now(timezone.utc),
                    )
                    for _ in range(n)
                ]
                s.add_all(jobs)
                await s.commit()
                job_ids = [j.id for j in jobs]

            factory = async_sessionmaker(engine, expire_on_commit=False)
            started = time.monotonic()
            results = await asyncio.gather(
                *(run_report_job(j, session_factory=factory, storage=report_storage) for j in job_ids)
            )
            wall = time.monotonic() - started

            assert all(r is ReportStatus.succeeded for r in results)
            assert wall < sleep_s * n * 0.6, f"wall {wall:.2f}s looks serial, not concurrent"

            async with Session() as s:
                rows = (
                    await s.execute(select(ReportJob).where(ReportJob.id.in_(job_ids)))
                ).scalars().all()
            windows = sorted((r.started_at, r.finished_at) for r in rows)
            max_overlap = max(
                sum(1 for st, fi in windows if st <= start < fi) for start, _ in windows
            )
            assert max_overlap >= 2, "no [started_at, finished_at] windows overlapped"
        finally:
            async with Session() as s:
                if job_ids:
                    await s.execute(delete(ReportJob).where(ReportJob.id.in_(job_ids)))
                if user_id is not None:
                    # A succeeded job pushes an in-app "Report ready" notification
                    # for the requester — clear it before the user row goes.
                    from app.notifications.models import Notification

                    await s.execute(delete(Notification).where(Notification.user_id == user_id))
                if patient_id is not None:
                    await s.execute(delete(Patient).where(Patient.id == patient_id))
                if user_id is not None:
                    await s.execute(delete(User).where(User.id == user_id))
                await s.commit()
            await engine.dispose()


class TestRetrieval:
    async def test_lists_newest_first_and_filters_by_status(
        self, client, admin_headers, sample_patient, enqueued_jobs, run_job
    ):
        a = await _submit(client, admin_headers, str(sample_patient.id))
        b = await _submit(client, admin_headers, str(sample_patient.id))
        await run_job(UUID(b["id"]))  # b succeeds, a stays queued

        page = (await client.get(BASE, headers=admin_headers)).json()
        assert [i["id"] for i in page["items"]][:2] == [b["id"], a["id"]]

        succeeded = (await client.get(f"{BASE}?status=succeeded", headers=admin_headers)).json()
        assert b["id"] in [i["id"] for i in succeeded["items"]]
        assert a["id"] not in [i["id"] for i in succeeded["items"]]

    async def test_unknown_job_is_404(self, client, admin_headers):
        assert (await client.get(f"{BASE}/{UNKNOWN}", headers=admin_headers)).status_code == 404
        assert (await client.get(f"{BASE}/{UNKNOWN}/result", headers=admin_headers)).status_code == 404

    async def test_reading_requires_read_permission(self, client):
        # No token at all -> 401 (there is no role with generate-but-not-read).
        assert (await client.get(BASE)).status_code == 401

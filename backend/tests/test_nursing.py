"""Nursing records — minimal vitals scaffold.

Covers: create, list-by-patient, list-by-appointment, patient linkage, the
acting nurse + timestamp being recorded automatically, RBAC (nurse can,
receptionist cannot, anonymous cannot), empty list, invalid patient/visit,
basic non-clinical validation, and that the added appointments-by-patient
endpoint doesn't disturb the existing appointment flow.
"""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.appointments.models import Appointment, AppointmentChannel
from app.core.security import hash_password
from app.roles.models import Role
from app.users.models import User

BASE = "/api/v1/nursing"
UNKNOWN = "00000000-0000-0000-0000-000000000000"


async def _user_with_role(db_session, seeded_roles, *, code: str, email: str) -> User:
    role = (await db_session.execute(select(Role).where(Role.code == code))).scalar_one()
    user = User(
        employee_code=f"TEST-{code[:4].upper()}-N1", full_name=f"Test {code.title()}",
        email=email, role_id=role.id, password_hash=hash_password("TestPass123!"),
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def nurse_headers(client, db_session, seeded_roles) -> dict:
    await _user_with_role(db_session, seeded_roles, code="nurse", email="nurse@example.com")
    return await _login(client, "nurse@example.com")


@pytest_asyncio.fixture
async def receptionist_headers(client, db_session, seeded_roles) -> dict:
    # receptionist has patients.read / appointments.* but NO nursing.*
    await _user_with_role(db_session, seeded_roles, code="receptionist", email="front@example.com")
    return await _login(client, "front@example.com")


@pytest_asyncio.fixture
async def appointment(db_session, sample_patient, doctor_user) -> Appointment:
    appt = Appointment(
        patient_id=sample_patient.id,
        doctor_id=doctor_user.id,
        scheduled_at=datetime.now(timezone.utc),
        visit_type="IVF Consultation",
        channel=AppointmentChannel.WALK_IN,
    )
    db_session.add(appt)
    await db_session.commit()
    return appt


def _body(patient_id, **over):
    b = {
        "patient_id": str(patient_id),
        "blood_pressure_systolic": 120,
        "blood_pressure_diastolic": 80,
        "temperature": 98.4,
        "notes": "Patient comfortable, no complaints.",
    }
    b.update(over)
    return b


# --------------------------------------------------------------------------- #
# Create + the auto-recorded fields
# --------------------------------------------------------------------------- #

class TestCreate:
    async def test_create_record(self, client, nurse_headers, sample_patient):
        r = await client.post(f"{BASE}/records", json=_body(sample_patient.id), headers=nurse_headers)
        assert r.status_code == 201, r.text
        b = r.json()
        assert b["patient_id"] == str(sample_patient.id)      # individual patient, not couple
        assert b["appointment_id"] is None
        assert b["blood_pressure_systolic"] == 120
        assert b["blood_pressure_diastolic"] == 80
        assert float(b["temperature"]) == 98.4
        assert b["notes"] == "Patient comfortable, no complaints."

    async def test_logged_in_user_is_recorded_as_the_nurse(self, client, nurse_headers, db_session, sample_patient):
        r = await client.post(f"{BASE}/records", json=_body(sample_patient.id), headers=nurse_headers)
        b = r.json()
        nurse = (await db_session.execute(select(User).where(User.email == "nurse@example.com"))).scalar_one()
        assert b["recorded_by_id"] == str(nurse.id)
        assert b["recorded_by_name"] == nurse.full_name   # resolved via FK, not stored

    async def test_timestamp_is_recorded_automatically(self, client, nurse_headers, sample_patient):
        before = datetime.now(timezone.utc)
        b = (await client.post(f"{BASE}/records", json=_body(sample_patient.id), headers=nurse_headers)).json()
        after = datetime.now(timezone.utc)
        assert b["recorded_at"] and b["created_at"]
        recorded = datetime.fromisoformat(b["recorded_at"].replace("Z", "+00:00"))
        assert before.replace(microsecond=0) <= recorded <= after.replace(microsecond=0) or abs((recorded - before).total_seconds()) < 5

    async def test_links_to_the_visit_when_given(self, client, nurse_headers, sample_patient, appointment):
        r = await client.post(
            f"{BASE}/records",
            json=_body(sample_patient.id, appointment_id=str(appointment.id)),
            headers=nurse_headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["appointment_id"] == str(appointment.id)

    async def test_notes_only_record_is_allowed(self, client, nurse_headers, sample_patient):
        r = await client.post(
            f"{BASE}/records",
            json={"patient_id": str(sample_patient.id), "notes": "Awaiting doctor."},
            headers=nurse_headers,
        )
        assert r.status_code == 201, r.text
        b = r.json()
        assert b["blood_pressure_systolic"] is None and b["temperature"] is None


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #

class TestRetrieval:
    async def test_list_for_patient_newest_first(self, client, nurse_headers, sample_patient):
        first = (await client.post(f"{BASE}/records", json=_body(sample_patient.id, notes="first"), headers=nurse_headers)).json()
        second = (await client.post(f"{BASE}/records", json=_body(sample_patient.id, notes="second"), headers=nurse_headers)).json()

        r = await client.get(f"{BASE}/patients/{sample_patient.id}/records", headers=nurse_headers)
        assert r.status_code == 200
        ids = [row["id"] for row in r.json()]
        assert ids[:2] == [second["id"], first["id"]]

    async def test_list_for_appointment(self, client, nurse_headers, sample_patient, appointment):
        linked = (await client.post(
            f"{BASE}/records", json=_body(sample_patient.id, appointment_id=str(appointment.id)), headers=nurse_headers
        )).json()
        await client.post(f"{BASE}/records", json=_body(sample_patient.id), headers=nurse_headers)  # unlinked

        r = await client.get(f"{BASE}/appointments/{appointment.id}/records", headers=nurse_headers)
        assert r.status_code == 200
        rows = r.json()
        assert [row["id"] for row in rows] == [linked["id"]]

    async def test_patient_with_no_records_returns_empty_list(self, client, nurse_headers, sample_patient):
        r = await client.get(f"{BASE}/patients/{sample_patient.id}/records", headers=nurse_headers)
        assert r.status_code == 200
        assert r.json() == []

    async def test_doctor_can_view(self, client, nurse_headers, auth_headers, sample_patient):
        await client.post(f"{BASE}/records", json=_body(sample_patient.id), headers=nurse_headers)
        r = await client.get(f"{BASE}/patients/{sample_patient.id}/records", headers=auth_headers)  # auth_headers = doctor
        assert r.status_code == 200
        assert len(r.json()) == 1


# --------------------------------------------------------------------------- #
# RBAC
# --------------------------------------------------------------------------- #

class TestRbac:
    async def test_anonymous_cannot_create_or_read(self, client, sample_patient):
        pid = str(sample_patient.id)  # capture before requests (shared async session)
        assert (await client.post(f"{BASE}/records", json=_body(pid))).status_code == 401
        assert (await client.get(f"{BASE}/patients/{pid}/records")).status_code == 401

    async def test_role_without_nursing_permission_is_forbidden(self, client, receptionist_headers, sample_patient):
        pid = str(sample_patient.id)
        assert (
            await client.post(f"{BASE}/records", json=_body(pid), headers=receptionist_headers)
        ).status_code == 403
        assert (
            await client.get(f"{BASE}/patients/{pid}/records", headers=receptionist_headers)
        ).status_code == 403


# --------------------------------------------------------------------------- #
# Validation + bad references
# --------------------------------------------------------------------------- #

class TestValidationAndErrors:
    async def test_unknown_patient_is_404(self, client, nurse_headers):
        r = await client.post(f"{BASE}/records", json=_body(UNKNOWN), headers=nurse_headers)
        assert r.status_code == 404
        assert r.json()["error_code"] == "patient_not_found"

    async def test_unknown_appointment_is_404(self, client, nurse_headers, sample_patient):
        r = await client.post(
            f"{BASE}/records", json=_body(sample_patient.id, appointment_id=UNKNOWN), headers=nurse_headers
        )
        assert r.status_code == 404

    async def test_appointment_of_another_patient_is_rejected(
        self, client, nurse_headers, db_session, appointment, seeded_roles
    ):
        from app.patients.models import Patient

        other = Patient(uhid="TEST-2026-09999", full_name="Other Patient", gender="male")
        db_session.add(other)
        await db_session.commit()

        r = await client.post(
            f"{BASE}/records",
            json=_body(other.id, appointment_id=str(appointment.id)),
            headers=nurse_headers,
        )
        assert r.status_code == 422
        assert r.json()["error_code"] == "appointment_patient_mismatch"

    async def test_non_numeric_and_negative_values_are_rejected(self, client, nurse_headers, sample_patient):
        pid = str(sample_patient.id)
        assert (
            await client.post(
                f"{BASE}/records",
                json={"patient_id": pid, "blood_pressure_systolic": "high"},
                headers=nurse_headers,
            )
        ).status_code == 422
        assert (
            await client.post(
                f"{BASE}/records",
                json={"patient_id": pid, "temperature": -3},
                headers=nurse_headers,
            )
        ).status_code == 422

    async def test_completely_empty_record_is_rejected(self, client, nurse_headers, sample_patient):
        r = await client.post(
            f"{BASE}/records", json={"patient_id": str(sample_patient.id)}, headers=nurse_headers
        )
        assert r.status_code == 422


# --------------------------------------------------------------------------- #
# Existing appointment flow still works
# --------------------------------------------------------------------------- #

class TestExistingFlowUnbroken:
    async def test_appointments_by_patient_endpoint(self, client, auth_headers, sample_patient, appointment):
        r = await client.get(f"/api/v1/appointments/by-patient/{sample_patient.id}", headers=auth_headers)
        assert r.status_code == 200
        assert [a["id"] for a in r.json()] == [str(appointment.id)]

    async def test_day_appointment_list_still_works(self, client, auth_headers):
        r = await client.get("/api/v1/appointments", headers=auth_headers)
        assert r.status_code == 200

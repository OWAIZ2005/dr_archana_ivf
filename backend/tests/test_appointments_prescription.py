"""
Front-desk / prescription-department role split.

Front desk keeps same-day operations (book, check in, cancel today's
visit, mark it complete) but no longer owns anything ahead of the visit
day — the future-appointments list and reminder follow-ups moved to a new
`prescription` role. Both roles can mark a visit COMPLETED, since
prescription (dispensing) is the actual last step of a real visit.
"""
from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.appointments.models import Appointment, AppointmentChannel, AppointmentStatus
from app.core.security import hash_password
from app.patients.models import Patient
from app.roles.models import Role
from app.users.models import User


async def _make_user(db_session: AsyncSession, *, role_code: str, email: str, employee_code: str) -> User:
    role = (await db_session.execute(select(Role).where(Role.code == role_code))).scalar_one()
    user = User(
        employee_code=employee_code, full_name=f"Test {role_code.title()}", email=email,
        role_id=role.id, password_hash=hash_password("TestPass123!"),
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient, email: str) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass123!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _receptionist(db_session, seeded_roles):
    return await _make_user(db_session, role_code="receptionist", email="reception@example.com", employee_code="TEST-REC-001")


async def _prescription(db_session, seeded_roles):
    return await _make_user(db_session, role_code="prescription", email="prescription@example.com", employee_code="TEST-RX-001")


async def _arrived_appointment(db_session: AsyncSession, doctor: User) -> Appointment:
    patient = Patient(uhid="TEST-2026-00099", full_name="Test Patient", gender="female")
    db_session.add(patient)
    await db_session.flush()
    appt = Appointment(
        patient_id=patient.id, doctor_id=doctor.id,
        scheduled_at=datetime.now(timezone.utc), visit_type="Consultation",
        channel=AppointmentChannel.WALK_IN, status=AppointmentStatus.ARRIVED,
    )
    db_session.add(appt)
    await db_session.commit()
    return appt


async def test_prescription_role_exists_with_expected_permissions(db_session: AsyncSession, seeded_roles):
    role = (await db_session.execute(select(Role).where(Role.code == "prescription"))).scalar_one()
    codes = {p.code for p in role.permissions}
    assert "appointments.manage_future" in codes
    assert "reminders.manage" in codes
    assert "appointments.complete" in codes


async def test_receptionist_lost_future_and_reminders(db_session: AsyncSession, seeded_roles):
    role = (await db_session.execute(select(Role).where(Role.code == "receptionist"))).scalar_one()
    codes = {p.code for p in role.permissions}
    assert "appointments.manage_future" not in codes
    assert "reminders.manage" not in codes
    # But still keeps same-day operations, including the new complete action.
    assert "appointments.complete" in codes
    assert "appointments.checkin" in codes


async def test_receptionist_cannot_list_future_appointments(client: AsyncClient, db_session: AsyncSession, seeded_roles):
    user = await _receptionist(db_session, seeded_roles)
    headers = await _login(client, user.email)
    resp = await client.get("/api/v1/appointments/future", headers=headers)
    assert resp.status_code == 403


async def test_prescription_can_list_future_appointments(client: AsyncClient, db_session: AsyncSession, seeded_roles):
    user = await _prescription(db_session, seeded_roles)
    headers = await _login(client, user.email)
    resp = await client.get("/api/v1/appointments/future", headers=headers)
    assert resp.status_code == 200


async def test_receptionist_can_mark_appointment_completed(client: AsyncClient, db_session: AsyncSession, seeded_roles):
    receptionist = await _receptionist(db_session, seeded_roles)
    appt = await _arrived_appointment(db_session, receptionist)
    headers = await _login(client, receptionist.email)
    resp = await client.post(f"/api/v1/appointments/{appt.id}/status", json={"status": "completed"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"


async def test_prescription_can_mark_appointment_completed(client: AsyncClient, db_session: AsyncSession, seeded_roles):
    prescription = await _prescription(db_session, seeded_roles)
    appt = await _arrived_appointment(db_session, prescription)
    headers = await _login(client, prescription.email)
    resp = await client.post(f"/api/v1/appointments/{appt.id}/status", json={"status": "completed"}, headers=headers)
    assert resp.status_code == 200, resp.text


async def test_role_without_complete_permission_is_rejected(client: AsyncClient, db_session: AsyncSession, seeded_roles):
    """embryologist has neither appointments.complete nor a reason to —
    confirms the /status endpoint's per-target-status check actually
    blocks, not just happens to pass for the two roles above."""
    embryologist = await _make_user(db_session, role_code="embryologist", email="embryo@example.com", employee_code="TEST-EMB-001")
    doctor = await _make_user(db_session, role_code="doctor", email="doc-for-embryo-test@example.com", employee_code="TEST-DOC-099")
    appt = await _arrived_appointment(db_session, doctor)
    headers = await _login(client, embryologist.email)
    resp = await client.post(f"/api/v1/appointments/{appt.id}/status", json={"status": "completed"}, headers=headers)
    assert resp.status_code == 403

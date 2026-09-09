"""GET /prescriptions/{id}/pdf — printable prescription PDF.

Reuses the report-PDF test approach (pypdf text extraction). The PDF is
generated from the already-saved prescription; nothing is written back.
"""
import re
from io import BytesIO

import pytest
import pytest_asyncio
from httpx import AsyncClient
from pypdf import PdfReader
from sqlalchemy import select

from app.core.security import hash_password
from app.roles.models import Role
from app.users.models import User

BASE = "/api/v1/prescriptions"
UNKNOWN = "00000000-0000-0000-0000-000000000000"

LINES = [
    {
        "medicine_name": "Tab. Folic Acid 5mg", "dosage": "5 mg", "frequency": "1-0-0",
        "timing": "After food", "duration": "30 days",
        "instructions": "Continue through the stimulation phase and into early pregnancy if conception occurs.",
    },
    {
        "medicine_name": "Inj. Gonal-F 300IU", "dosage": "150 IU", "frequency": "0-0-1",
        "timing": "Evening", "duration": "5 days", "instructions": "Subcutaneous; rotate injection sites.",
    },
]


async def _create_prescription(client: AsyncClient, headers: dict, patient_id: str, *, lines=None) -> dict:
    r = await client.post(
        BASE,
        headers=headers,
        json={
            "patient_id": patient_id,
            "category": "Green",
            "notes": "Review after cycle day 12.",
            "lines": lines if lines is not None else LINES,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _pdf_text(content: bytes) -> str:
    """Extracted PDF text with all runs of whitespace collapsed to single
    spaces — table cells wrap across lines, so raw newlines would split
    multi-word values."""
    raw = "\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(content)).pages)
    return re.sub(r"\s+", " ", raw)


@pytest_asyncio.fixture
async def receptionist_headers(client, db_session, seeded_roles) -> dict:
    # receptionist has patients.read / appointments.* but NOT clinical.read
    role = (await db_session.execute(select(Role).where(Role.code == "receptionist"))).scalar_one()
    db_session.add(User(
        employee_code="TEST-RX-FRONT", full_name="Front Desk", email="frontdesk@example.com",
        role_id=role.id, password_hash=hash_password("TestPass123!"),
    ))
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"email": "frontdesk@example.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestPrescriptionPdf:
    async def test_returns_pdf_for_authorized_user(self, client, auth_headers, doctor_user, sample_patient):
        rx = await _create_prescription(client, auth_headers, str(sample_patient.id))

        r = await client.get(f"{BASE}/{rx['id']}/pdf", headers=auth_headers)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        cd = r.headers["content-disposition"]
        assert cd.startswith("inline; ")
        assert cd.endswith(f'prescription_{sample_patient.uhid}_{rx["created_at"][:10]}.pdf"')
        assert r.content.startswith(b"%PDF-")
        assert r.content.rstrip().endswith(b"%%EOF")

    async def test_pdf_contains_header_and_medicine_data(self, client, auth_headers, doctor_user, sample_patient):
        rx = await _create_prescription(client, auth_headers, str(sample_patient.id))
        r = await client.get(f"{BASE}/{rx['id']}/pdf", headers=auth_headers)
        text = _pdf_text(r.content)

        # header block
        assert sample_patient.full_name in text          # patient name
        assert sample_patient.uhid in text               # patient UHID
        assert doctor_user.full_name in text             # prescribing doctor name
        assert "Prescription" in text
        assert "Doctor Signature" in text
        # prescription date, formatted the same way the PDF does (%d %b %Y)
        from datetime import datetime
        pdate = datetime.fromisoformat(rx["created_at"].replace("Z", "+00:00")).strftime("%d %b %Y")
        assert pdate in text

        # medicine rows: name + dosage/frequency/timing/duration/instructions
        assert "Folic Acid" in text and "Gonal-F" in text          # multiple medicines
        assert "5 mg" in text and "150 IU" in text                  # dosage
        assert "1-0-0" in text and "0-0-1" in text                  # frequency
        assert "30 days" in text and "5 days" in text               # duration
        assert "After food" in text and "Evening" in text           # timing
        assert "rotate injection sites" in text                     # instructions
        assert "Review after cycle day 12" in text                  # prescription notes

    async def test_long_single_medicine_still_renders_valid_pdf(self, client, auth_headers, doctor_user, sample_patient):
        rx = await _create_prescription(
            client, auth_headers, str(sample_patient.id),
            lines=[{
                "medicine_name": "Tab. Very Long Named Medication With Extended Strength 12.5mg",
                "dosage": "12.5 mg", "frequency": "1-1-1", "timing": "After food",
                "duration": "90 days",
                "instructions": ("Take with a full glass of water. " * 12).strip(),
            }],
        )
        r = await client.get(f"{BASE}/{rx['id']}/pdf", headers=auth_headers)
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF-") and r.content.rstrip().endswith(b"%%EOF")
        assert "Very Long Named Medication" in _pdf_text(r.content)

    async def test_generating_pdf_does_not_mutate_the_prescription(self, client, auth_headers, doctor_user, sample_patient):
        rx = await _create_prescription(client, auth_headers, str(sample_patient.id))
        before = (await client.get(f"{BASE}/{rx['id']}", headers=auth_headers)).json()
        await client.get(f"{BASE}/{rx['id']}/pdf", headers=auth_headers)
        after = (await client.get(f"{BASE}/{rx['id']}", headers=auth_headers)).json()
        assert before == after


class TestPrescriptionPdfSecurity:
    async def test_anonymous_is_rejected(self, client, auth_headers, doctor_user, sample_patient):
        rx = await _create_prescription(client, auth_headers, str(sample_patient.id))
        assert (await client.get(f"{BASE}/{rx['id']}/pdf")).status_code == 401

    async def test_role_without_clinical_read_is_forbidden(
        self, client, auth_headers, receptionist_headers, doctor_user, sample_patient
    ):
        rx = await _create_prescription(client, auth_headers, str(sample_patient.id))
        rid = rx["id"]
        # same gate as GET /prescriptions/{id} (clinical.read) — a role without it
        # cannot fetch the PDF by guessing the id.
        assert (await client.get(f"{BASE}/{rid}", headers=receptionist_headers)).status_code == 403
        assert (await client.get(f"{BASE}/{rid}/pdf", headers=receptionist_headers)).status_code == 403

    async def test_unknown_prescription_is_404(self, client, auth_headers):
        assert (await client.get(f"{BASE}/{UNKNOWN}/pdf", headers=auth_headers)).status_code == 404


class TestExistingPrescriptionFlowUnbroken:
    async def test_create_and_view_still_work(self, client, auth_headers, doctor_user, sample_patient):
        rx = await _create_prescription(client, auth_headers, str(sample_patient.id))
        assert len(rx["lines"]) == 2
        assert rx["prescribed_by_id"] == str(doctor_user.id)

        got = (await client.get(f"{BASE}/{rx['id']}", headers=auth_headers)).json()
        assert got["id"] == rx["id"]
        assert {l["medicine_name"] for l in got["lines"]} == {"Tab. Folic Acid 5mg", "Inj. Gonal-F 300IU"}

        listed = (await client.get(f"{BASE}/by-patient/{sample_patient.id}", headers=auth_headers)).json()
        assert rx["id"] in [p["id"] for p in listed]

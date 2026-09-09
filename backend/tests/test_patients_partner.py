"""GET /patients/{id}/partner — navigate from one individual patient to their
linked partner via the existing Couple relationship. No schema change; each
patient stays a separate record with its own medical data.
"""
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.roles.models import Role
from app.users.models import User


async def _make_couple(client: AsyncClient, headers: dict, *, wife="Priya Raman", husband="Arjun Kumar") -> dict:
    resp = await client.post(
        "/api/v1/patients/couples",
        headers=headers,
        json={
            "female_patient": {"full_name": wife, "gender": "female"},
            "male_patient": {"full_name": husband, "gender": "male"},
            "infertility_type": "Primary Infertility",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestPartnerLookup:
    async def test_female_patient_returns_male_partner(self, client, admin_headers):
        couple = await _make_couple(client, admin_headers)
        female_id = couple["female_patient"]["id"]

        resp = await client.get(f"/api/v1/patients/{female_id}/partner", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["couple_id"] == couple["id"]
        assert body["patient_role"] == "female"
        assert body["partner_role"] == "male"
        assert body["partner"]["id"] == couple["male_patient"]["id"]
        assert body["partner"]["full_name"] == "Arjun Kumar"
        assert body["partner"]["uhid"] == couple["male_patient"]["uhid"]
        assert body["partner"]["gender"] == "male"

    async def test_male_patient_returns_female_partner(self, client, admin_headers):
        couple = await _make_couple(client, admin_headers)
        male_id = couple["male_patient"]["id"]

        body = (await client.get(f"/api/v1/patients/{male_id}/partner", headers=admin_headers)).json()
        assert body["patient_role"] == "male"
        assert body["partner_role"] == "female"
        assert body["partner"]["id"] == couple["female_patient"]["id"]
        assert body["partner"]["full_name"] == "Priya Raman"
        assert body["partner"]["uhid"] == couple["female_patient"]["uhid"]

    async def test_either_side_points_at_the_other_individual_record(self, client, admin_headers):
        couple = await _make_couple(client, admin_headers, wife="Lena Roy", husband="Sam Roy")
        f, m = couple["female_patient"]["id"], couple["male_patient"]["id"]
        assert f != m

        from_f = (await client.get(f"/api/v1/patients/{f}/partner", headers=admin_headers)).json()
        from_m = (await client.get(f"/api/v1/patients/{m}/partner", headers=admin_headers)).json()
        assert from_f["partner"]["id"] == m
        assert from_m["partner"]["id"] == f
        assert from_f["couple_id"] == from_m["couple_id"] == couple["id"]

    async def test_patient_with_no_partner_returns_null(self, client, admin_headers, sample_patient):
        resp = await client.get(f"/api/v1/patients/{sample_patient.id}/partner", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() is None

    async def test_unknown_patient_is_404(self, client, admin_headers):
        resp = await client.get(
            "/api/v1/patients/00000000-0000-0000-0000-000000000000/partner", headers=admin_headers
        )
        assert resp.status_code == 404

    async def test_response_carries_only_partner_identity_not_medical_data(self, client, admin_headers):
        couple = await _make_couple(client, admin_headers)
        body = (
            await client.get(f"/api/v1/patients/{couple['female_patient']['id']}/partner", headers=admin_headers)
        ).json()
        # PatientSummary shape only — no lab results, consultations, medications, etc.
        assert set(body["partner"].keys()) <= {
            "id", "uhid", "full_name", "date_of_birth", "gender", "blood_group",
            "nationality", "is_international", "photo_document_id", "phone", "email",
            "allergies", "created_at",
        }


class TestPartnerRbac:
    async def test_requires_authentication(self, client, admin_headers):
        couple = await _make_couple(client, admin_headers)
        resp = await client.get(f"/api/v1/patients/{couple['female_patient']['id']}/partner")
        assert resp.status_code == 401

    async def test_requires_patients_read_permission(self, client, admin_headers, db_session, seeded_roles):
        couple = await _make_couple(client, admin_headers)

        role = (
            await db_session.execute(select(Role).where(Role.code == "it_administrator"))
        ).scalar_one()  # has admin.* / audit.read / reports.read, NOT patients.read
        db_session.add(User(
            employee_code="TEST-ITA-PARTNER", full_name="IT Admin", email="ita-partner@example.com",
            role_id=role.id, password_hash=hash_password("TestPass123!"),
        ))
        await db_session.commit()
        token = (
            await client.post(
                "/api/v1/auth/login",
                json={"email": "ita-partner@example.com", "password": "TestPass123!"},
            )
        ).json()["access_token"]

        resp = await client.get(
            f"/api/v1/patients/{couple['female_patient']['id']}/partner",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestExistingBehaviourUnchanged:
    async def test_patient_list_still_returns_individuals(self, client, admin_headers):
        couple = await _make_couple(client, admin_headers, wife="Indira Nair", husband="Vikram Nair")
        rows = (await client.get("/api/v1/patients", headers=admin_headers)).json()
        names = {r["full_name"] for r in rows}
        # Two separate individual rows, never a combined "Indira Nair - Vikram Nair".
        assert "Indira Nair" in names and "Vikram Nair" in names
        assert not any(" - " in r["full_name"] for r in rows)

    async def test_couple_registration_still_creates_two_patients_and_link(self, client, admin_headers):
        couple = await _make_couple(client, admin_headers, wife="Meera Das", husband="Anil Das")
        assert couple["female_patient"]["id"] != couple["male_patient"]["id"]
        assert couple["female_patient"]["uhid"] != couple["male_patient"]["uhid"]
        # still retrievable via the pre-existing couple endpoint
        got = (
            await client.get(
                f"/api/v1/patients/couples/by-patient/{couple['male_patient']['id']}", headers=admin_headers
            )
        ).json()
        assert got["id"] == couple["id"]

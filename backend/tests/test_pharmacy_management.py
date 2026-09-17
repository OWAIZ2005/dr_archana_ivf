"""Pharmacy Management module — vendors, medicine CRUD/attributes,
purchase entry -> GRN (stock creation), sales returns, and manual stock
adjustment. Extends the existing dispensing tests in test_pharmacy.py;
does not duplicate them.
"""
import uuid
from datetime import date, timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.patients.models import Patient
from app.pharmacy.models import Medicine, MedicineBatch
from app.roles.models import Role
from app.users.models import User

PHARM = "/api/v1/pharmacy"
PURCH = "/api/v1/purchasing"
UNKNOWN = "00000000-0000-0000-0000-000000000000"


@pytest_asyncio.fixture
async def viewer_headers(client: AsyncClient, db_session, seeded_roles) -> dict:
    """A signed-in user with pharmacy.read but none of the write perms
    (the nurse role) — used to prove read-only access is enforced."""
    role = (await db_session.execute(select(Role).where(Role.code == "nurse"))).scalar_one()
    db_session.add(User(
        employee_code="TEST-PHARM-VIEW", full_name="Pharmacy Viewer", email="pharmviewer@example.com",
        role_id=role.id, password_hash=hash_password("TestPass123!"),
    ))
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"email": "pharmviewer@example.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _mk_vendor(client, headers, name, **extra) -> dict:
    r = await client.post(f"{PURCH}/vendors", headers=headers, json={"name": name, "account_code": f"AC-{uuid.uuid4().hex[:8]}", **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_medicine(client, headers, name, **extra) -> dict:
    r = await client.post(f"{PHARM}/medicines", headers=headers, json={"generic_name": name, "unit": "Strip", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _purchase_line(medicine_id, **extra) -> dict:
    return {
        "medicine_id": medicine_id, "batch_number": "B-001", "quantity": 100, "free_quantity": 0,
        "purchase_rate_paise": 5000, "selling_price_paise": 8000, "discount_percent": 0,
        "expiry_date": str(date.today() + timedelta(days=400)), "hsn_code": "3004", "tax_percent": 12,
        **extra,
    }


class TestVendors:
    async def test_create_and_list_vendor(self, client: AsyncClient, admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "Apex Pharma Distributors", city="Chennai", gst_number="33AAAAA0000A1Z5")
        listed = (await client.get(f"{PURCH}/vendors", headers=admin_headers)).json()
        assert any(v["id"] == vendor["id"] for v in listed)
        assert vendor["payment_type"] == "credit"
        assert vendor["is_active"] is True

    async def test_duplicate_account_code_rejected(self, client: AsyncClient, admin_headers):
        v = await _mk_vendor(client, admin_headers, "Vendor A")
        r = await client.post(f"{PURCH}/vendors", headers=admin_headers, json={"name": "Vendor B", "account_code": v["account_code"]})
        assert r.status_code == 409

    async def test_update_vendor_fields_persist(self, client: AsyncClient, admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "Beta Pharma")
        r = await client.patch(f"{PURCH}/vendors/{vendor['id']}", headers=admin_headers, json={"city": "Mumbai", "credit_period_days": 45})
        assert r.status_code == 200, r.text
        assert r.json()["city"] == "Mumbai"
        assert r.json()["credit_period_days"] == 45

    async def test_viewer_without_vendor_manage_permission_is_forbidden(self, client: AsyncClient, viewer_headers):
        r = await client.post(f"{PURCH}/vendors", headers=viewer_headers, json={"name": "X", "account_code": "AC-X"})
        assert r.status_code == 403


class TestMedicineAttributesAndCrud:
    async def test_create_attribute_and_use_on_medicine(self, client: AsyncClient, admin_headers):
        attr = await client.post(f"{PHARM}/attributes", headers=admin_headers, json={"attribute_type": "medicine_type", "name": "Injection"})
        assert attr.status_code == 201, attr.text
        med = await _mk_medicine(client, admin_headers, "Recombinant FSH", medicine_type_id=attr.json()["id"])
        assert med["medicine_type_id"] == attr.json()["id"]

    async def test_duplicate_attribute_value_rejected(self, client: AsyncClient, admin_headers):
        await client.post(f"{PHARM}/attributes", headers=admin_headers, json={"attribute_type": "medicine_type", "name": "Tablet"})
        r = await client.post(f"{PHARM}/attributes", headers=admin_headers, json={"attribute_type": "medicine_type", "name": "Tablet"})
        assert r.status_code == 409

    async def test_deactivate_attribute(self, client: AsyncClient, admin_headers):
        attr = (await client.post(f"{PHARM}/attributes", headers=admin_headers, json={"attribute_type": "medicine_type", "name": "Gel"})).json()
        r = await client.patch(f"{PHARM}/attributes/{attr['id']}", headers=admin_headers, json={"is_active": False})
        assert r.status_code == 200
        active_only = (await client.get(f"{PHARM}/attributes?attribute_type=medicine_type", headers=admin_headers)).json()
        assert all(a["id"] != attr["id"] for a in active_only)
        with_inactive = (await client.get(f"{PHARM}/attributes?attribute_type=medicine_type&include_inactive=true", headers=admin_headers)).json()
        assert any(a["id"] == attr["id"] for a in with_inactive)

    async def test_create_medicine_and_edit_every_field(self, client: AsyncClient, admin_headers):
        med = await _mk_medicine(client, admin_headers, "Amoxicillin", brand_name="Amoxil", hsn_code="3004", gst_percent=5)
        r = await client.patch(
            f"{PHARM}/medicines/{med['id']}", headers=admin_headers,
            json={"brand_name": "Novamox", "manufacturer": "Cipla", "mrp_paise": 12000, "hsn_code": "30049099", "gst_percent": 12, "reorder_level": 50},
        )
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["brand_name"] == "Novamox"
        assert updated["manufacturer"] == "Cipla"
        assert updated["mrp_paise"] == 12000
        assert updated["hsn_code"] == "30049099"
        assert updated["gst_percent"] == 12
        assert updated["reorder_level"] == 50
        # Reflected on a fresh GET too, not just the response of the PATCH.
        refetched = (await client.get(f"{PHARM}/medicines/{med['id']}", headers=admin_headers)).json()
        assert refetched["manufacturer"] == "Cipla"

    async def test_deactivate_medicine(self, client: AsyncClient, admin_headers):
        med = await _mk_medicine(client, admin_headers, "Ibuprofen")
        r = await client.patch(f"{PHARM}/medicines/{med['id']}", headers=admin_headers, json={"is_active": False})
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_correct_batch_expiry_date(self, client: AsyncClient, admin_headers, db_session: AsyncSession):
        """The module's exact example: an expiry mis-keyed as 2026 instead
        of 2027 must be correctable without touching quantity/rate."""
        medicine = Medicine(generic_name="Letrozole", unit="Strip", reorder_level=10)
        db_session.add(medicine)
        await db_session.flush()
        wrong_date = date(2026, 9, 10)
        batch = MedicineBatch(
            medicine_id=medicine.id, batch_number="LZ-001", expiry_date=wrong_date,
            purchase_rate_paise=1000, selling_rate_paise=1500, quantity_received=20, quantity_available=20,
        )
        db_session.add(batch)
        await db_session.commit()

        corrected = str(date(2027, 9, 10))
        r = await client.patch(f"{PHARM}/batches/{batch.id}/expiry?expiry_date={corrected}", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["expiry_date"] == corrected
        assert r.json()["quantity_available"] == 20  # untouched

    async def test_viewer_cannot_manage_medicines(self, client: AsyncClient, viewer_headers):
        r = await client.post(f"{PHARM}/medicines", headers=viewer_headers, json={"generic_name": "X", "unit": "Vial"})
        assert r.status_code == 403


class TestPurchaseAndGRN:
    async def test_purchase_calculates_totals_and_receive_creates_batch_stock(self, client: AsyncClient, admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "Gamma Pharma")
        med = await _mk_medicine(client, admin_headers, "Metformin")

        line = _purchase_line(med["id"], quantity=100, free_quantity=10, purchase_rate_paise=5000, tax_percent=12, discount_percent=10)
        r = await client.post(
            f"{PHARM}/purchases", headers=admin_headers,
            json={"vendor_id": vendor["id"], "entry_date": str(date.today()), "invoice_number": "INV-1001", "lines": [line]},
        )
        assert r.status_code == 201, r.text
        purchase = r.json()
        assert purchase["status"] == "pending"

        # gross = 100*5000 = 500000; discount 10% = 50000; taxable = 450000;
        # tax 12% = 54000 (cgst 27000 + sgst 27000); net total = 504000.
        assert purchase["taxable_value_paise"] == 450000
        assert purchase["total_discount_paise"] == 50000
        assert purchase["cgst_paise"] == 27000
        assert purchase["sgst_paise"] == 27000
        assert purchase["total_value_paise"] == 504000

        # No stock exists yet — it's only a purchase entry, not received.
        stock_before = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert not any(row["medicine_id"] == med["id"] for row in stock_before)

        received = await client.post(f"{PHARM}/purchases/{purchase['id']}/receive", headers=admin_headers)
        assert received.status_code == 200, received.text
        assert received.json()["status"] == "completed"

        stock_after = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        row = next(r for r in stock_after if r["medicine_id"] == med["id"])
        assert row["quantity_available"] == 110  # 100 ordered + 10 free
        assert row["batch_number"] == "B-001"

    async def test_receiving_same_batch_again_tops_up_quantity(self, client: AsyncClient, admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "Delta Pharma")
        med = await _mk_medicine(client, admin_headers, "Azithromycin")

        for _ in range(2):
            r = await client.post(
                f"{PHARM}/purchases", headers=admin_headers,
                json={"vendor_id": vendor["id"], "entry_date": str(date.today()), "lines": [_purchase_line(med["id"], quantity=50, free_quantity=0)]},
            )
            purchase = r.json()
            await client.post(f"{PHARM}/purchases/{purchase['id']}/receive", headers=admin_headers)

        stock = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        rows = [r for r in stock if r["medicine_id"] == med["id"]]
        assert len(rows) == 1  # same batch number -> one batch row, topped up
        assert rows[0]["quantity_available"] == 100

    async def test_cannot_receive_a_purchase_twice(self, client: AsyncClient, admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "Epsilon Pharma")
        med = await _mk_medicine(client, admin_headers, "Doxycycline")
        purchase = (await client.post(
            f"{PHARM}/purchases", headers=admin_headers,
            json={"vendor_id": vendor["id"], "entry_date": str(date.today()), "lines": [_purchase_line(med["id"])]},
        )).json()
        await client.post(f"{PHARM}/purchases/{purchase['id']}/receive", headers=admin_headers)
        second = await client.post(f"{PHARM}/purchases/{purchase['id']}/receive", headers=admin_headers)
        assert second.status_code == 409

    async def test_viewer_cannot_create_or_receive_purchases(self, client: AsyncClient, admin_headers, viewer_headers):
        vendor = await _mk_vendor(client, admin_headers, "Zeta Pharma")
        med = await _mk_medicine(client, admin_headers, "Ranitidine")
        r = await client.post(
            f"{PHARM}/purchases", headers=viewer_headers,
            json={"vendor_id": vendor["id"], "entry_date": str(date.today()), "lines": [_purchase_line(med["id"])]},
        )
        assert r.status_code == 403


class TestSalesReturn:
    async def _dispense(self, client, admin_headers, patient_id, medicine_id, qty):
        r = await client.post(
            f"{PHARM}/dispense", headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
            json={"patient_id": patient_id, "lines": [{"medicine_id": medicine_id, "quantity": qty}]},
        )
        assert r.status_code == 201, r.text
        return r.json()

    async def test_return_restores_stock_and_marks_sale_returned(
        self, client: AsyncClient, admin_headers, db_session: AsyncSession, sample_patient: Patient
    ):
        medicine = Medicine(generic_name="Folic Acid", unit="Strip", reorder_level=5)
        db_session.add(medicine)
        await db_session.flush()
        db_session.add(MedicineBatch(
            medicine_id=medicine.id, batch_number="FA-001", expiry_date=date.today() + timedelta(days=200),
            purchase_rate_paise=500, selling_rate_paise=800, quantity_received=20, quantity_available=20,
        ))
        await db_session.commit()

        sale = await self._dispense(client, admin_headers, str(sample_patient.id), str(medicine.id), 5)
        stock_after_sale = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert next(r for r in stock_after_sale if r["medicine_id"] == str(medicine.id))["quantity_available"] == 15

        # SaleLineOut doesn't carry its own row id (medicine_id/batch_id/
        # quantity/unit_price_paise only) — look it up via the ORM, the
        # same as a UI would via the sale's line list.
        from app.pharmacy.models import PharmacySaleLine
        line_row = (await db_session.execute(
            select(PharmacySaleLine).where(PharmacySaleLine.sale_id == uuid.UUID(sale["id"]))
        )).scalar_one()

        r = await client.post(
            f"{PHARM}/sales/{sale['id']}/return", headers=admin_headers,
            json={"reason": "Patient did not need the full course", "lines": [{"sale_line_id": str(line_row.id), "quantity": 5}]},
        )
        assert r.status_code == 201, r.text
        assert r.json()["total_refund_paise"] == 5 * 800

        stock_after_return = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert next(r for r in stock_after_return if r["medicine_id"] == str(medicine.id))["quantity_available"] == 20

        detail = (await client.get(f"{PHARM}/sales/{sale['id']}", headers=admin_headers)).json()
        assert detail["status"] == "returned"

    async def test_return_quantity_cannot_exceed_sold(
        self, client: AsyncClient, admin_headers, db_session: AsyncSession, sample_patient: Patient
    ):
        medicine = Medicine(generic_name="Vitamin D3", unit="Strip", reorder_level=5)
        db_session.add(medicine)
        await db_session.flush()
        db_session.add(MedicineBatch(
            medicine_id=medicine.id, batch_number="VD-001", expiry_date=date.today() + timedelta(days=200),
            purchase_rate_paise=500, selling_rate_paise=700, quantity_received=10, quantity_available=10,
        ))
        await db_session.commit()

        sale = await self._dispense(client, admin_headers, str(sample_patient.id), str(medicine.id), 3)

        # Look up the real PharmacySaleLine id via the ORM (not exposed on
        # SaleLineOut). Captured as a plain string BEFORE any further HTTP
        # request — each request expires the shared session's objects, and
        # re-accessing an expired attribute afterwards triggers a lazy
        # reload outside the async greenlet (MissingGreenlet).
        from app.pharmacy.models import PharmacySaleLine
        line_row = (await db_session.execute(
            select(PharmacySaleLine).where(PharmacySaleLine.sale_id == uuid.UUID(sale["id"]))
        )).scalar_one()
        line_id = str(line_row.id)

        over = await client.post(
            f"{PHARM}/sales/{sale['id']}/return", headers=admin_headers,
            json={"lines": [{"sale_line_id": line_id, "quantity": 4}]},
        )
        assert over.status_code == 422
        assert over.json()["error_code"] == "return_quantity_exceeds_sold"

        ok = await client.post(
            f"{PHARM}/sales/{sale['id']}/return", headers=admin_headers,
            json={"lines": [{"sale_line_id": line_id, "quantity": 3}]},
        )
        assert ok.status_code == 201, ok.text
        assert ok.json()["total_refund_paise"] == 3 * 700

        stock = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert next(r for r in stock if r["medicine_id"] == str(medicine.id))["quantity_available"] == 10  # fully restored

        detail = (await client.get(f"{PHARM}/sales/{sale['id']}", headers=admin_headers)).json()
        assert detail["status"] == "returned"

    async def test_viewer_without_return_permission_is_forbidden(
        self, client: AsyncClient, admin_headers, viewer_headers, db_session: AsyncSession, sample_patient: Patient
    ):
        medicine = Medicine(generic_name="Zinc", unit="Strip", reorder_level=5)
        db_session.add(medicine)
        await db_session.flush()
        db_session.add(MedicineBatch(
            medicine_id=medicine.id, batch_number="ZN-001", expiry_date=date.today() + timedelta(days=200),
            purchase_rate_paise=500, selling_rate_paise=700, quantity_received=10, quantity_available=10,
        ))
        await db_session.commit()
        sale = await self._dispense(client, admin_headers, str(sample_patient.id), str(medicine.id), 2)

        from app.pharmacy.models import PharmacySaleLine
        line_row = (await db_session.execute(
            select(PharmacySaleLine).where(PharmacySaleLine.sale_id == uuid.UUID(sale["id"]))
        )).scalar_one()

        # nurse role has pharmacy.read but not pharmacy.return
        r = await client.post(
            f"{PHARM}/sales/{sale['id']}/return", headers=viewer_headers,
            json={"lines": [{"sale_line_id": str(line_row.id), "quantity": 1}]},
        )
        assert r.status_code == 403


class TestStockAdjustment:
    async def test_adjustment_updates_quantity_and_records_difference(self, client: AsyncClient, admin_headers, db_session: AsyncSession):
        medicine = Medicine(generic_name="Calcium Carbonate", unit="Strip", reorder_level=5)
        db_session.add(medicine)
        await db_session.flush()
        batch = MedicineBatch(
            medicine_id=medicine.id, batch_number="CC-001", expiry_date=date.today() + timedelta(days=200),
            purchase_rate_paise=400, selling_rate_paise=600, quantity_received=40, quantity_available=40,
        )
        db_session.add(batch)
        await db_session.commit()

        r = await client.post(
            f"{PHARM}/stock/adjust", headers=admin_headers,
            json={"batch_id": str(batch.id), "physical_stock": 35, "reason": "Physical count during audit"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["system_stock"] == 40
        assert body["physical_stock"] == 35
        assert body["difference"] == -5

        stock = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert next(row for row in stock if row["batch_id"] == str(batch.id))["quantity_available"] == 35

    async def test_viewer_without_adjust_permission_is_forbidden(self, client: AsyncClient, viewer_headers, db_session: AsyncSession):
        medicine = Medicine(generic_name="Magnesium", unit="Strip", reorder_level=5)
        db_session.add(medicine)
        await db_session.flush()
        batch = MedicineBatch(
            medicine_id=medicine.id, batch_number="MG-001", expiry_date=date.today() + timedelta(days=200),
            purchase_rate_paise=400, selling_rate_paise=600, quantity_received=10, quantity_available=10,
        )
        db_session.add(batch)
        await db_session.commit()

        r = await client.post(f"{PHARM}/stock/adjust", headers=viewer_headers, json={"batch_id": str(batch.id), "physical_stock": 5})
        assert r.status_code == 403

    async def test_unauthenticated_cannot_adjust_stock(self, client: AsyncClient):
        r = await client.post(f"{PHARM}/stock/adjust", json={"batch_id": UNKNOWN, "physical_stock": 5})
        assert r.status_code == 401

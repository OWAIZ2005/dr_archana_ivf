"""Pharmacy Phases 2-4 — Medicine Templates, Purchase Returns, Purchase
Orders. Extends the existing pharmacy test suites; does not duplicate
Phase 1 (Indents) or the earlier Medicine/Vendor/Purchase/Billing tests.
"""
import uuid
from datetime import date, timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.pharmacy.models import Medicine, MedicineBatch
from app.roles.models import Role
from app.users.models import User

PHARM = "/api/v1/pharmacy"
PURCH = "/api/v1/purchasing"
UNKNOWN = "00000000-0000-0000-0000-000000000000"


@pytest_asyncio.fixture
async def viewer_headers(client: AsyncClient, db_session, seeded_roles) -> dict:
    role = (await db_session.execute(select(Role).where(Role.code == "nurse"))).scalar_one()
    db_session.add(User(
        employee_code="TEST-P246-VIEW", full_name="Read Only Nurse", email="p246viewer@example.com",
        role_id=role.id, password_hash=hash_password("TestPass123!"),
    ))
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"email": "p246viewer@example.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def second_admin_headers(client: AsyncClient, db_session, seeded_roles) -> dict:
    """A second administrator — used to approve a PO the first admin
    created (approver must not equal requester)."""
    role = (await db_session.execute(select(Role).where(Role.code == "administrator"))).scalar_one()
    db_session.add(User(
        employee_code="TEST-P246-ADMIN2", full_name="Second Admin", email="p246admin2@example.com",
        role_id=role.id, password_hash=hash_password("TestPass123!"),
    ))
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"email": "p246admin2@example.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _mk_medicine(client, headers, name, **extra) -> dict:
    r = await client.post(f"{PHARM}/medicines", headers=headers, json={"generic_name": name, "unit": "Strip", **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_vendor(client, headers, name) -> dict:
    r = await client.post(f"{PURCH}/vendors", headers=headers, json={"name": name, "account_code": f"AC-{uuid.uuid4().hex[:8]}"})
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_and_receive_purchase(client, headers, vendor_id, medicine_id, quantity=100, batch="B-RET-001") -> tuple[dict, str]:
    r = await client.post(
        f"{PHARM}/purchases", headers=headers,
        json={"vendor_id": vendor_id, "entry_date": str(date.today()), "lines": [{
            "medicine_id": medicine_id, "batch_number": batch, "quantity": quantity, "free_quantity": 0,
            "purchase_rate_paise": 5000, "selling_price_paise": 8000, "discount_percent": 0,
            "expiry_date": str(date.today() + timedelta(days=300)), "hsn_code": "3004", "tax_percent": 12,
        }]},
    )
    assert r.status_code == 201, r.text
    purchase = r.json()
    received = await client.post(f"{PHARM}/purchases/{purchase['id']}/receive", headers=headers)
    assert received.status_code == 200, received.text
    return received.json(), purchase["lines"][0]["id"]


# --------------------------------------------------------------------------- #
# Phase 2 — Medicine Templates
# --------------------------------------------------------------------------- #

class TestMedicineTemplates:
    async def test_create_template_add_and_persist_medicines(self, client: AsyncClient, admin_headers):
        med_a = await _mk_medicine(client, admin_headers, "Paracetamol 500mg")
        med_b = await _mk_medicine(client, admin_headers, "Ceftriaxone 1g")

        r = await client.post(
            f"{PHARM}/templates", headers=admin_headers,
            json={"name": f"OT Kit {uuid.uuid4().hex[:6]}", "description": "Standard OT restock", "items": [
                {"medicine_id": med_a["id"], "default_quantity": 10}, {"medicine_id": med_b["id"], "default_quantity": 5},
            ]},
        )
        assert r.status_code == 201, r.text
        template = r.json()
        assert template["status"] == "ACTIVE"
        assert len(template["items"]) == 2

        # Persists across a fresh GET (simulating a page refresh).
        fetched = (await client.get(f"{PHARM}/templates/{template['id']}", headers=admin_headers)).json()
        assert len(fetched["items"]) == 2
        assert {i["default_quantity"] for i in fetched["items"]} == {10, 5}
        return template, med_a, med_b

    async def test_edit_quantity_and_remove_medicine_persist(self, client: AsyncClient, admin_headers):
        med_a = await _mk_medicine(client, admin_headers, "Normal Saline 500ml")
        med_b = await _mk_medicine(client, admin_headers, "Syringe 5ml")
        template = (await client.post(
            f"{PHARM}/templates", headers=admin_headers,
            json={"name": f"Injection Kit {uuid.uuid4().hex[:6]}", "items": [{"medicine_id": med_a["id"], "default_quantity": 10}, {"medicine_id": med_b["id"], "default_quantity": 20}]},
        )).json()
        item_a = next(i for i in template["items"] if i["medicine_id"] == med_a["id"])
        item_b = next(i for i in template["items"] if i["medicine_id"] == med_b["id"])

        updated = await client.patch(f"{PHARM}/templates/{template['id']}/items/{item_a['id']}", headers=admin_headers, json={"quantity": 15})
        assert updated.status_code == 200, updated.text
        assert next(i["default_quantity"] for i in updated.json()["items"] if i["id"] == item_a["id"]) == 15

        removed = await client.delete(f"{PHARM}/templates/{template['id']}/items/{item_b['id']}", headers=admin_headers)
        assert removed.status_code == 200
        assert len(removed.json()["items"]) == 1

        fetched = (await client.get(f"{PHARM}/templates/{template['id']}", headers=admin_headers)).json()
        assert len(fetched["items"]) == 1
        assert fetched["items"][0]["default_quantity"] == 15

    async def test_deactivate_and_reactivate_template(self, client: AsyncClient, admin_headers):
        template = (await client.post(f"{PHARM}/templates", headers=admin_headers, json={"name": f"Emergency Kit {uuid.uuid4().hex[:6]}", "items": []})).json()
        off = await client.patch(f"{PHARM}/templates/{template['id']}", headers=admin_headers, json={"status": "INACTIVE"})
        assert off.json()["status"] == "INACTIVE"
        active_only = (await client.get(f"{PHARM}/templates?status=ACTIVE", headers=admin_headers)).json()
        assert all(t["id"] != template["id"] for t in active_only)

        on = await client.patch(f"{PHARM}/templates/{template['id']}", headers=admin_headers, json={"status": "ACTIVE"})
        assert on.json()["status"] == "ACTIVE"

    async def test_duplicate_template_name_rejected(self, client: AsyncClient, admin_headers):
        name = f"Dup Kit {uuid.uuid4().hex[:6]}"
        await client.post(f"{PHARM}/templates", headers=admin_headers, json={"name": name, "items": []})
        r = await client.post(f"{PHARM}/templates", headers=admin_headers, json={"name": name, "items": []})
        assert r.status_code == 409

    async def test_viewer_cannot_manage_templates(self, client: AsyncClient, viewer_headers):
        r = await client.post(f"{PHARM}/templates", headers=viewer_headers, json={"name": "X", "items": []})
        assert r.status_code == 403


# --------------------------------------------------------------------------- #
# Phase 3 — Purchase Returns
# --------------------------------------------------------------------------- #

class TestPurchaseReturns:
    async def test_purchase_grn_then_return_decreases_stock(self, client: AsyncClient, admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "Return Test Vendor")
        medicine = await _mk_medicine(client, admin_headers, "Cetrotide 0.25mg")
        purchase, line_id = await _mk_and_receive_purchase(client, admin_headers, vendor["id"], medicine["id"], quantity=100)

        stock_before = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert next(r for r in stock_before if r["medicine_id"] == medicine["id"])["quantity_available"] == 100

        returnable = (await client.get(f"{PHARM}/purchases/{purchase['id']}/returnable", headers=admin_headers)).json()
        assert returnable[0]["returnable"] == 100

        r = await client.post(f"{PHARM}/purchases/{purchase['id']}/return", headers=admin_headers, json={"reason": "Damaged in transit", "lines": [{"purchase_line_id": line_id, "quantity": 20}]})
        assert r.status_code == 201, r.text
        assert r.json()["items"][0]["quantity"] == 20

        stock_after = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert next(r for r in stock_after if r["medicine_id"] == medicine["id"])["quantity_available"] == 80

        history = (await client.get(f"{PHARM}/purchase-returns", headers=admin_headers)).json()
        assert any(x["purchase_id"] == purchase["id"] for x in history)

    async def test_maximum_return_validation_100_20_80_then_1_fails(self, client: AsyncClient, admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "Max Return Vendor")
        medicine = await _mk_medicine(client, admin_headers, "Duphaston 10mg")
        purchase, line_id = await _mk_and_receive_purchase(client, admin_headers, vendor["id"], medicine["id"], quantity=100)

        first = await client.post(f"{PHARM}/purchases/{purchase['id']}/return", headers=admin_headers, json={"lines": [{"purchase_line_id": line_id, "quantity": 20}]})
        assert first.status_code == 201, first.text

        second = await client.post(f"{PHARM}/purchases/{purchase['id']}/return", headers=admin_headers, json={"lines": [{"purchase_line_id": line_id, "quantity": 80}]})
        assert second.status_code == 201, second.text

        returnable = (await client.get(f"{PHARM}/purchases/{purchase['id']}/returnable", headers=admin_headers)).json()
        assert returnable[0]["returnable"] == 0

        third = await client.post(f"{PHARM}/purchases/{purchase['id']}/return", headers=admin_headers, json={"lines": [{"purchase_line_id": line_id, "quantity": 1}]})
        assert third.status_code == 422
        assert third.json()["error_code"] == "return_exceeds_purchased"

    async def test_cannot_return_against_a_purchase_not_yet_received(self, client: AsyncClient, admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "Unreceived Vendor")
        medicine = await _mk_medicine(client, admin_headers, "HCG 5000IU")
        r = await client.post(
            f"{PHARM}/purchases", headers=admin_headers,
            json={"vendor_id": vendor["id"], "entry_date": str(date.today()), "lines": [{
                "medicine_id": medicine["id"], "batch_number": "B-X", "quantity": 10, "free_quantity": 0,
                "purchase_rate_paise": 100, "selling_price_paise": 200, "discount_percent": 0,
                "expiry_date": str(date.today() + timedelta(days=100)), "hsn_code": None, "tax_percent": 0,
            }]},
        )
        purchase = r.json()
        line_id = purchase["lines"][0]["id"]
        ret = await client.post(f"{PHARM}/purchases/{purchase['id']}/return", headers=admin_headers, json={"lines": [{"purchase_line_id": line_id, "quantity": 1}]})
        assert ret.status_code == 409
        assert ret.json()["error_code"] == "purchase_not_received"

    async def test_viewer_without_return_permission_is_forbidden(self, client: AsyncClient, admin_headers, viewer_headers):
        vendor = await _mk_vendor(client, admin_headers, "RBAC Vendor")
        medicine = await _mk_medicine(client, admin_headers, "Gonal-F 300IU")
        purchase, line_id = await _mk_and_receive_purchase(client, admin_headers, vendor["id"], medicine["id"], quantity=10)
        r = await client.post(f"{PHARM}/purchases/{purchase['id']}/return", headers=viewer_headers, json={"lines": [{"purchase_line_id": line_id, "quantity": 1}]})
        assert r.status_code == 403


# --------------------------------------------------------------------------- #
# Phase 4 — Purchase Orders
# --------------------------------------------------------------------------- #

class TestPurchaseOrders:
    async def test_po_lifecycle_draft_to_fully_received(self, client: AsyncClient, admin_headers, second_admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "PO Vendor")
        medicine = await _mk_medicine(client, admin_headers, "Progesterone 400mg")

        created = await client.post(
            f"{PHARM}/purchase-orders", headers=admin_headers,
            json={"vendor_id": vendor["id"], "po_date": str(date.today()), "items": [{"medicine_id": medicine["id"], "ordered_quantity": 100, "purchase_rate_paise": 5000, "tax_percent": 12}]},
        )
        assert created.status_code == 201, created.text
        po = created.json()
        assert po["status"] == "DRAFT"

        # PO creation must NOT touch stock.
        stock = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert not any(r["medicine_id"] == medicine["id"] for r in stock)

        edited = await client.patch(f"{PHARM}/purchase-orders/{po['id']}", headers=admin_headers, json={"notes": "Urgent restock"})
        assert edited.status_code == 200
        assert edited.json()["notes"] == "Urgent restock"

        submitted = await client.post(f"{PHARM}/purchase-orders/{po['id']}/submit", headers=admin_headers)
        assert submitted.json()["status"] == "PENDING_APPROVAL"

        self_approve = await client.post(f"{PHARM}/purchase-orders/{po['id']}/approve", headers=admin_headers)
        assert self_approve.status_code == 409
        assert self_approve.json()["error_code"] == "self_approval_blocked"

        approved = await client.post(f"{PHARM}/purchase-orders/{po['id']}/approve", headers=second_admin_headers)
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"

        # PO approval must NOT touch stock either.
        stock = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert not any(r["medicine_id"] == medicine["id"] for r in stock)

        item_id = po["items"][0]["id"]
        partial = await client.post(
            f"{PHARM}/purchase-orders/{po['id']}/receive", headers=admin_headers,
            json={"lines": [{"po_item_id": item_id, "quantity": 60, "batch_number": "PO-B1", "expiry_date": str(date.today() + timedelta(days=300)), "selling_price_paise": 8000}]},
        )
        assert partial.status_code == 200, partial.text
        assert partial.json()["status"] == "PARTIALLY_RECEIVED"
        assert partial.json()["items"][0]["received_quantity"] == 60

        stock_after_partial = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert next(r for r in stock_after_partial if r["medicine_id"] == medicine["id"])["quantity_available"] == 60

        full = await client.post(
            f"{PHARM}/purchase-orders/{po['id']}/receive", headers=admin_headers,
            json={"lines": [{"po_item_id": item_id, "quantity": 40, "batch_number": "PO-B1", "expiry_date": str(date.today() + timedelta(days=300)), "selling_price_paise": 8000}]},
        )
        assert full.status_code == 200, full.text
        assert full.json()["status"] == "FULLY_RECEIVED"
        assert full.json()["items"][0]["received_quantity"] == 100

        stock_final = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        matching = [r for r in stock_final if r["medicine_id"] == medicine["id"]]
        assert len(matching) == 1  # same batch number -> topped up, not duplicated
        assert matching[0]["quantity_available"] == 100

    async def test_cannot_over_receive_beyond_remaining(self, client: AsyncClient, admin_headers, second_admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "Over Receive Vendor")
        medicine = await _mk_medicine(client, admin_headers, "Folic Acid 5mg")
        po = (await client.post(
            f"{PHARM}/purchase-orders", headers=admin_headers,
            json={"vendor_id": vendor["id"], "po_date": str(date.today()), "items": [{"medicine_id": medicine["id"], "ordered_quantity": 50, "purchase_rate_paise": 1000}]},
        )).json()
        await client.post(f"{PHARM}/purchase-orders/{po['id']}/submit", headers=admin_headers)
        await client.post(f"{PHARM}/purchase-orders/{po['id']}/approve", headers=second_admin_headers)

        item_id = po["items"][0]["id"]
        over = await client.post(
            f"{PHARM}/purchase-orders/{po['id']}/receive", headers=admin_headers,
            json={"lines": [{"po_item_id": item_id, "quantity": 51, "batch_number": "OB-1", "expiry_date": str(date.today() + timedelta(days=100)), "selling_price_paise": 1500}]},
        )
        assert over.status_code == 422
        assert over.json()["error_code"] == "receive_exceeds_remaining"

    async def test_cancel_po_does_not_change_stock(self, client: AsyncClient, admin_headers):
        vendor = await _mk_vendor(client, admin_headers, "Cancel Vendor")
        medicine = await _mk_medicine(client, admin_headers, "Metformin 500mg")
        po = (await client.post(
            f"{PHARM}/purchase-orders", headers=admin_headers,
            json={"vendor_id": vendor["id"], "po_date": str(date.today()), "items": [{"medicine_id": medicine["id"], "ordered_quantity": 20, "purchase_rate_paise": 500}]},
        )).json()
        cancelled = await client.post(f"{PHARM}/purchase-orders/{po['id']}/cancel", headers=admin_headers)
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "CANCELLED"

        stock = (await client.get(f"{PHARM}/stock", headers=admin_headers)).json()
        assert not any(r["medicine_id"] == medicine["id"] for r in stock)

        blocked = await client.post(f"{PHARM}/purchase-orders/{po['id']}/submit", headers=admin_headers)
        assert blocked.status_code == 409

    async def test_viewer_cannot_create_or_approve_po(self, client: AsyncClient, admin_headers, viewer_headers):
        vendor = await _mk_vendor(client, admin_headers, "RBAC PO Vendor")
        medicine = await _mk_medicine(client, admin_headers, "Ibuprofen 400mg")
        r = await client.post(
            f"{PHARM}/purchase-orders", headers=viewer_headers,
            json={"vendor_id": vendor["id"], "po_date": str(date.today()), "items": [{"medicine_id": medicine["id"], "ordered_quantity": 10, "purchase_rate_paise": 100}]},
        )
        assert r.status_code == 403


# --------------------------------------------------------------------------- #
# Phase 6 — Settings & Indent Templates (smoke tests)
# --------------------------------------------------------------------------- #

class TestSettingsAndIndentTemplates:
    async def test_settings_persist_across_requests(self, client: AsyncClient, admin_headers):
        updated = await client.put(f"{PHARM}/settings", headers=admin_headers, json={"pharmacy_name": "Test Pharmacy Name", "gstin": "33AAAAA0000A1Z5", "show_mrp": False})
        assert updated.status_code == 200, updated.text
        fetched = (await client.get(f"{PHARM}/settings", headers=admin_headers)).json()
        assert fetched["pharmacy_name"] == "Test Pharmacy Name"
        assert fetched["gstin"] == "33AAAAA0000A1Z5"
        assert fetched["show_mrp"] is False

    async def test_indent_template_crud_and_duplicate(self, client: AsyncClient, admin_headers):
        medicine = await _mk_medicine(client, admin_headers, "IV Cannula 20G")
        created = await client.post(
            f"{PHARM}/indent-templates", headers=admin_headers,
            json={"name": f"OT Restock {uuid.uuid4().hex[:6]}", "department": "OT", "items": [{"medicine_id": medicine["id"], "default_quantity": 15}]},
        )
        assert created.status_code == 201, created.text
        template = created.json()
        assert template["items"][0]["default_quantity"] == 15

        duped = await client.post(f"{PHARM}/indent-templates/{template['id']}/duplicate", headers=admin_headers)
        assert duped.status_code == 201, duped.text
        assert duped.json()["name"] == f"{template['name']} (Copy)"
        assert len(duped.json()["items"]) == 1

        deactivated = await client.patch(f"{PHARM}/indent-templates/{template['id']}", headers=admin_headers, json={"status": "INACTIVE"})
        assert deactivated.json()["status"] == "INACTIVE"

    async def test_viewer_cannot_change_settings_or_manage_indent_templates(self, client: AsyncClient, viewer_headers):
        r1 = await client.put(f"{PHARM}/settings", headers=viewer_headers, json={"pharmacy_name": "Hacked"})
        assert r1.status_code == 403
        r2 = await client.post(f"{PHARM}/indent-templates", headers=viewer_headers, json={"name": "X", "items": []})
        assert r2.status_code == 403

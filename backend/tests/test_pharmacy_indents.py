"""Pharmacy Indents — department request -> pharmacist delivery (full and
partial) -> stock decrease -> optional return -> stock restored.
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
UNKNOWN = "00000000-0000-0000-0000-000000000000"


@pytest_asyncio.fixture
async def viewer_headers(client: AsyncClient, db_session, seeded_roles) -> dict:
    """Nurse role: has pharmacy.indent_request but NOT pharmacy.indent_deliver —
    the exact "department can ask, only the pharmacist can fulfil" split."""
    role = (await db_session.execute(select(Role).where(Role.code == "nurse"))).scalar_one()
    db_session.add(User(
        employee_code="TEST-INDENT-NURSE", full_name="Ward Nurse", email="wardnurse@example.com",
        role_id=role.id, password_hash=hash_password("TestPass123!"),
    ))
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"email": "wardnurse@example.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _mk_medicine_with_stock(db_session, *, qty: int, generic_name: str = "Syringe 5ml") -> Medicine:
    medicine = Medicine(generic_name=generic_name, unit="Piece", reorder_level=5)
    db_session.add(medicine)
    await db_session.flush()
    if qty > 0:
        db_session.add(MedicineBatch(
            medicine_id=medicine.id, batch_number="B-STK-001", expiry_date=date.today() + timedelta(days=300),
            purchase_rate_paise=500, selling_rate_paise=800, quantity_received=qty, quantity_available=qty,
        ))
    await db_session.commit()
    return medicine


async def _create_indent(client, headers, medicine_id: str, requested_quantity: int, **extra) -> dict:
    r = await client.post(
        f"{PHARM}/indents", headers=headers,
        json={
            "department": "OT", "room": "OT-1", "request_date": str(date.today()),
            "items": [{"medicine_id": medicine_id, "requested_quantity": requested_quantity}], **extra,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


class TestIndentRequest:
    async def test_create_indent_defaults_to_pending(self, client: AsyncClient, viewer_headers, db_session):
        medicine = await _mk_medicine_with_stock(db_session, qty=50)
        indent = await _create_indent(client, viewer_headers, str(medicine.id), 20)
        assert indent["status"] == "PENDING"
        assert indent["department"] == "OT"
        assert indent["items"][0]["requested_quantity"] == 20
        assert indent["items"][0]["delivered_quantity"] == 0

    async def test_list_indents_filters_by_status_and_department(self, client: AsyncClient, admin_headers, viewer_headers, db_session):
        medicine = await _mk_medicine_with_stock(db_session, qty=50, generic_name="Gauze Roll")
        await _create_indent(client, viewer_headers, str(medicine.id), 5, department="Ward 2")
        listed = (await client.get(f"{PHARM}/indents?department=Ward", headers=admin_headers)).json()
        assert any(i["department"] == "Ward 2" for i in listed)
        pending = (await client.get(f"{PHARM}/indents?status=PENDING", headers=admin_headers)).json()
        assert all(i["status"] == "PENDING" for i in pending)

    async def test_available_stock_endpoint_reflects_batches(self, client: AsyncClient, admin_headers, db_session):
        medicine = await _mk_medicine_with_stock(db_session, qty=33, generic_name="IV Cannula")
        r = await client.get(f"{PHARM}/indents/stock/available?medicine_id={medicine.id}", headers=admin_headers)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert rows[0]["available"] == 33


class TestIndentDelivery:
    async def test_full_delivery_marks_delivered_and_decreases_stock(self, client: AsyncClient, admin_headers, viewer_headers, db_session):
        medicine = await _mk_medicine_with_stock(db_session, qty=50, generic_name="Normal Saline 500ml")
        indent = await _create_indent(client, viewer_headers, str(medicine.id), 10)
        item_id = indent["items"][0]["id"]

        r = await client.post(f"{PHARM}/indents/{indent['id']}/deliver", headers=admin_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 10}]})
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["status"] == "DELIVERED"
        assert updated["items"][0]["delivered_quantity"] == 10

        stock = (await client.get(f"{PHARM}/indents/stock/available?medicine_id={medicine.id}", headers=admin_headers)).json()
        assert stock[0]["available"] == 40

    async def test_partial_delivery_then_second_delivery_completes_it(self, client: AsyncClient, admin_headers, viewer_headers, db_session):
        """Requested: 10, Available: 6 -> deliver 6 -> Partially Delivered,
        remaining 4 stays visible/deliverable -> deliver the rest -> Delivered."""
        medicine = await _mk_medicine_with_stock(db_session, qty=6, generic_name="Injection Ceftriaxone")
        indent = await _create_indent(client, viewer_headers, str(medicine.id), 10)
        item_id = indent["items"][0]["id"]

        first = await client.post(f"{PHARM}/indents/{indent['id']}/deliver", headers=admin_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 6}]})
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "PARTIALLY_DELIVERED"
        assert first.json()["items"][0]["delivered_quantity"] == 6

        # Receive more stock, then deliver the remaining 4.
        db_batch = MedicineBatch(
            medicine_id=medicine.id, batch_number="B-STK-002", expiry_date=date.today() + timedelta(days=200),
            purchase_rate_paise=500, selling_rate_paise=800, quantity_received=4, quantity_available=4,
        )
        db_session.add(db_batch)
        await db_session.commit()

        second = await client.post(f"{PHARM}/indents/{indent['id']}/deliver", headers=admin_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 4}]})
        assert second.status_code == 200, second.text
        assert second.json()["status"] == "DELIVERED"
        assert second.json()["items"][0]["delivered_quantity"] == 10

    async def test_cannot_deliver_more_than_requested(self, client: AsyncClient, admin_headers, viewer_headers, db_session):
        medicine = await _mk_medicine_with_stock(db_session, qty=50, generic_name="Cotton Roll")
        indent = await _create_indent(client, viewer_headers, str(medicine.id), 5)
        item_id = indent["items"][0]["id"]
        r = await client.post(f"{PHARM}/indents/{indent['id']}/deliver", headers=admin_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 6}]})
        assert r.status_code == 422
        assert r.json()["error_code"] == "delivery_exceeds_requested"

    async def test_cannot_deliver_more_than_available_stock(self, client: AsyncClient, admin_headers, viewer_headers, db_session):
        medicine = await _mk_medicine_with_stock(db_session, qty=2, generic_name="Adrenaline Ampoule")
        indent = await _create_indent(client, viewer_headers, str(medicine.id), 10)
        item_id = indent["items"][0]["id"]
        r = await client.post(f"{PHARM}/indents/{indent['id']}/deliver", headers=admin_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 5}]})
        assert r.status_code == 409
        assert r.json()["error_code"] == "insufficient_stock"

    async def test_viewer_without_deliver_permission_is_forbidden(self, client: AsyncClient, viewer_headers, db_session):
        medicine = await _mk_medicine_with_stock(db_session, qty=50, generic_name="Bandage")
        indent = await _create_indent(client, viewer_headers, str(medicine.id), 5)
        item_id = indent["items"][0]["id"]
        r = await client.post(f"{PHARM}/indents/{indent['id']}/deliver", headers=viewer_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 5}]})
        assert r.status_code == 403

    async def test_unauthenticated_cannot_create_indent(self, client: AsyncClient):
        r = await client.post(f"{PHARM}/indents", json={"department": "OT", "request_date": str(date.today()), "items": []})
        assert r.status_code == 401


class TestIndentReturn:
    async def test_return_restores_stock_and_caps_status(self, client: AsyncClient, admin_headers, viewer_headers, db_session):
        medicine = await _mk_medicine_with_stock(db_session, qty=20, generic_name="Foley Catheter")
        indent = await _create_indent(client, viewer_headers, str(medicine.id), 10)
        item_id = indent["items"][0]["id"]
        await client.post(f"{PHARM}/indents/{indent['id']}/deliver", headers=admin_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 10}]})

        stock_after_delivery = (await client.get(f"{PHARM}/indents/stock/available?medicine_id={medicine.id}", headers=admin_headers)).json()
        assert stock_after_delivery[0]["available"] == 10

        r = await client.post(f"{PHARM}/indents/{indent['id']}/return", headers=admin_headers, json={"reason": "Unused", "lines": [{"indent_item_id": item_id, "quantity": 10}]})
        assert r.status_code == 201, r.text

        stock_after_return = (await client.get(f"{PHARM}/indents/stock/available?medicine_id={medicine.id}", headers=admin_headers)).json()
        assert stock_after_return[0]["available"] == 20

        detail = (await client.get(f"{PHARM}/indents/{indent['id']}", headers=admin_headers)).json()
        assert detail["status"] == "RETURNED"
        assert detail["items"][0]["returned_quantity"] == 10

    async def test_cannot_return_more_than_delivered(self, client: AsyncClient, admin_headers, viewer_headers, db_session):
        medicine = await _mk_medicine_with_stock(db_session, qty=20, generic_name="Suture Kit")
        indent = await _create_indent(client, viewer_headers, str(medicine.id), 10)
        item_id = indent["items"][0]["id"]
        await client.post(f"{PHARM}/indents/{indent['id']}/deliver", headers=admin_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 4}]})

        over = await client.post(f"{PHARM}/indents/{indent['id']}/return", headers=admin_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 5}]})
        assert over.status_code == 422
        assert over.json()["error_code"] == "return_exceeds_delivered"

        ok = await client.post(f"{PHARM}/indents/{indent['id']}/return", headers=admin_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 4}]})
        assert ok.status_code == 201, ok.text

    async def test_viewer_without_deliver_permission_cannot_process_return(self, client: AsyncClient, admin_headers, viewer_headers, db_session):
        medicine = await _mk_medicine_with_stock(db_session, qty=20, generic_name="Blood Set")
        indent = await _create_indent(client, viewer_headers, str(medicine.id), 5)
        item_id = indent["items"][0]["id"]
        await client.post(f"{PHARM}/indents/{indent['id']}/deliver", headers=admin_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 5}]})
        r = await client.post(f"{PHARM}/indents/{indent['id']}/return", headers=viewer_headers, json={"lines": [{"indent_item_id": item_id, "quantity": 1}]})
        assert r.status_code == 403

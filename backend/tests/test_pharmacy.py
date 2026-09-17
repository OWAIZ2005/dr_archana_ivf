"""
Pharmacy dispensing tests — FEFO batch selection and stock-insufficiency
rejection (spec §15/§33).
"""
import uuid
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.patients.models import Patient
from app.pharmacy.models import Medicine, MedicineBatch


async def _seed_medicine_with_batches(db_session: AsyncSession) -> Medicine:
    medicine = Medicine(generic_name="Gonal-F", unit="Pen", reorder_level=20)
    db_session.add(medicine)
    await db_session.flush()

    # Two batches: an older-expiry one with limited stock, and a
    # later-expiry one with plenty — FEFO must drain the older one first.
    db_session.add_all([
        MedicineBatch(
            medicine_id=medicine.id, batch_number="OLD-001", expiry_date=date.today() + timedelta(days=30),
            purchase_rate_paise=300000, selling_rate_paise=345000, quantity_received=5, quantity_available=5,
        ),
        MedicineBatch(
            medicine_id=medicine.id, batch_number="NEW-001", expiry_date=date.today() + timedelta(days=365),
            purchase_rate_paise=300000, selling_rate_paise=345000, quantity_received=50, quantity_available=50,
        ),
    ])
    await db_session.commit()
    return medicine


async def test_dispense_uses_fefo_batch_first(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, sample_patient: Patient
):
    medicine = await _seed_medicine_with_batches(db_session)

    resp = await client.post(
        "/api/v1/pharmacy/dispense", headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"patient_id": str(sample_patient.id), "lines": [{"medicine_id": str(medicine.id), "quantity": 3}]},
    )
    assert resp.status_code == 201, resp.text
    sale = resp.json()

    # All 3 units must come from the OLD batch (expires sooner), not NEW.
    assert len(sale["lines"]) == 1
    line = sale["lines"][0]
    assert line["quantity"] == 3


async def test_dispense_splits_across_batches_when_needed(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, sample_patient: Patient
):
    medicine = await _seed_medicine_with_batches(db_session)  # OLD has only 5 units

    resp = await client.post(
        "/api/v1/pharmacy/dispense", headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"patient_id": str(sample_patient.id), "lines": [{"medicine_id": str(medicine.id), "quantity": 8}]},
    )
    assert resp.status_code == 201, resp.text
    sale = resp.json()

    # 8 requested > OLD's 5 available -> must split: 5 from OLD + 3 from NEW.
    assert len(sale["lines"]) == 2
    total_dispensed = sum(l["quantity"] for l in sale["lines"])
    assert total_dispensed == 8


async def test_dispense_rejects_when_stock_insufficient(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, sample_patient: Patient
):
    medicine = await _seed_medicine_with_batches(db_session)  # total available: 55

    resp = await client.post(
        "/api/v1/pharmacy/dispense", headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={"patient_id": str(sample_patient.id), "lines": [{"medicine_id": str(medicine.id), "quantity": 999}]},
    )
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "insufficient_stock"


async def test_dispense_never_goes_negative_and_rolls_back_on_partial_failure(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, sample_patient: Patient
):
    """Two-line request where line 1 succeeds but line 2 has insufficient
    stock — the WHOLE transaction must roll back, per spec §33: a failure
    partway through a multi-line dispense must not leave line 1's stock
    deduction committed while line 2 silently fails."""
    medicine = await _seed_medicine_with_batches(db_session)
    other_medicine = Medicine(generic_name="Cetrotide", unit="Vial", reorder_level=5)
    db_session.add(other_medicine)
    await db_session.flush()
    db_session.add(MedicineBatch(
        medicine_id=other_medicine.id, batch_number="CET-001", expiry_date=date.today() + timedelta(days=180),
        purchase_rate_paise=100000, selling_rate_paise=128000, quantity_received=2, quantity_available=2,
    ))
    await db_session.commit()

    resp = await client.post(
        "/api/v1/pharmacy/dispense", headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": str(sample_patient.id),
            "lines": [
                {"medicine_id": str(medicine.id), "quantity": 3},        # would succeed alone
                {"medicine_id": str(other_medicine.id), "quantity": 999},  # fails — insufficient
            ],
        },
    )
    assert resp.status_code == 409

    # Stock for the FIRST medicine must be untouched — the failed second
    # line rolled the whole request back.
    stock_check = await client.get("/api/v1/pharmacy/medicines", headers=admin_headers)
    gonal_f = next(m for m in stock_check.json() if m["id"] == str(medicine.id))
    assert gonal_f["total_available"] == 55


async def test_dispense_applies_discount_and_records_payment_method(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, sample_patient: Patient
):
    medicine = await _seed_medicine_with_batches(db_session)  # OLD batch sells at 345000 paise/unit

    resp = await client.post(
        "/api/v1/pharmacy/dispense", headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": str(sample_patient.id),
            "lines": [{"medicine_id": str(medicine.id), "quantity": 2}],
            "discount_paise": 50000,
            "payment_method": "card",
        },
    )
    assert resp.status_code == 201, resp.text
    sale = resp.json()
    # gross = 2 * 345000 = 690000; net = 690000 - 50000 = 640000
    assert sale["discount_paise"] == 50000
    assert sale["total_amount_paise"] == 640000
    assert sale["payment_method"] == "card"

    fetched = await client.get(f"/api/v1/pharmacy/sales/{sale['id']}", headers=admin_headers)
    assert fetched.json()["payment_method"] == "card"


async def test_dispense_rejects_discount_larger_than_bill(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, sample_patient: Patient
):
    medicine = await _seed_medicine_with_batches(db_session)

    resp = await client.post(
        "/api/v1/pharmacy/dispense", headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": str(sample_patient.id),
            "lines": [{"medicine_id": str(medicine.id), "quantity": 1}],
            "discount_paise": 999999999,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "discount_exceeds_total"


async def test_dispense_rejects_invalid_payment_method(
    client: AsyncClient, admin_headers: dict, db_session: AsyncSession, sample_patient: Patient
):
    medicine = await _seed_medicine_with_batches(db_session)

    resp = await client.post(
        "/api/v1/pharmacy/dispense", headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "patient_id": str(sample_patient.id),
            "lines": [{"medicine_id": str(medicine.id), "quantity": 1}],
            "payment_method": "bitcoin",
        },
    )
    assert resp.status_code == 422

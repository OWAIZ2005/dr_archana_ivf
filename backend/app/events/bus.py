"""
Event names (the vocabulary from the enterprise spec §10) and the
`emit()` helper every service module calls to write to the outbox
within its own transaction.
"""
import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.events.models import OutboxEvent


class EventType(StrEnum):
    APPOINTMENT_CHECKED_IN = "AppointmentCheckedIn"
    APPOINTMENT_CANCELLED = "AppointmentCancelled"
    CLINICAL_SERVICE_COMPLETED = "ClinicalServiceCompleted"
    SCAN_COMPLETED = "ScanCompleted"
    INJECTION_ADMINISTERED = "InjectionAdministered"
    PAYMENT_RECEIVED = "PaymentReceived"
    PAYMENT_REFUNDED = "PaymentRefunded"
    MEDICINE_DISPENSED = "MedicineDispensed"
    STOCK_BELOW_REORDER_LEVEL = "StockBelowReorderLevel"
    ASSET_MOVED = "AssetMoved"
    MAINTENANCE_DUE = "MaintenanceDue"
    OT_CHECKLIST_INCOMPLETE = "OTChecklistIncomplete"
    EMBRYO_TRANSFER_COMPLETED = "EmbryoTransferCompleted"
    CRYO_MOVEMENT_RECORDED = "CryoMovementRecorded"
    PATIENT_REGISTERED = "PatientRegistered"
    LEAVE_REQUEST_SUBMITTED = "LeaveRequestSubmitted"
    PURCHASE_ORDER_APPROVED = "PurchaseOrderApproved"
    PHARMACY_STOCK_RECEIVED = "PharmacyStockReceived"
    PHARMACY_SALE_RETURNED = "PharmacySaleReturned"


async def emit(
    session: AsyncSession,
    *,
    event_type: EventType,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
) -> OutboxEvent:
    """Writes the event row in the caller's existing transaction. Does NOT
    commit — the caller's own commit (e.g. the request's get_db teardown)
    persists it atomically with whatever business change triggered it."""
    event = OutboxEvent(
        id=uuid.uuid4(),
        event_type=event_type.value,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event

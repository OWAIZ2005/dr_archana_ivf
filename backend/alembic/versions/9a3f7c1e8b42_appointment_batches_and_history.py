"""Front desk: configurable appointment batches (time-slot + visit-type
groupings) and an appointment_history audit trail for reschedules.

Additive only; no existing table/column touched except the new nullable
appointments.batch_id FK. Seeds the hospital's current default batch
configuration so today's front-desk dashboard groups correctly out of
the box; batches remain editable data, not hardcoded logic.

Revision ID: 9a3f7c1e8b42
Revises: 7c2e9d4a1b63
Create Date: 2026-09-18
"""
import uuid
from datetime import time

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "9a3f7c1e8b42"
down_revision = "7c2e9d4a1b63"
branch_labels = None
depends_on = None

DEFAULT_BATCHES = [
    ("09:00 AM - 10:00 AM — ANC / CD / RD", time(9, 0), time(10, 0), "ANC,CD,RD", 0),
    ("10:00 AM - 11:00 AM — IN / PR Scans", time(10, 0), time(11, 0), "IN,PR Scans", 1),
    ("11:00 AM - 12:00 PM — Prescription ET / EA", time(11, 0), time(12, 0), "Prescription ET,Prescription EA", 2),
    ("12:00 PM - 01:00 PM — Stimulation", time(12, 0), time(13, 0), "Stimulation", 3),
    ("04:00 PM - 06:00 PM — CN / CD", time(16, 0), time(18, 0), "CN,CD", 4),
]


def upgrade() -> None:
    op.create_table(
        "appointment_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("visit_types", sa.String(500), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_appointment_batches_is_active", "appointment_batches", ["is_active"])

    op.create_table(
        "appointment_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id"), nullable=False),
        sa.Column("old_scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("new_scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_appointment_history_appointment_id", "appointment_history", ["appointment_id"])

    op.add_column("appointments", sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointment_batches.id"), nullable=True))
    op.create_index("ix_appointments_batch_id", "appointments", ["batch_id"])

    batches_table = sa.table(
        "appointment_batches",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("start_time", sa.Time),
        sa.column("end_time", sa.Time),
        sa.column("visit_types", sa.String),
        sa.column("display_order", sa.Integer),
    )
    op.bulk_insert(batches_table, [
        {"id": uuid.uuid4(), "name": name, "start_time": start, "end_time": end, "visit_types": types, "display_order": order}
        for name, start, end, types, order in DEFAULT_BATCHES
    ])


def downgrade() -> None:
    op.drop_index("ix_appointments_batch_id", table_name="appointments")
    op.drop_column("appointments", "batch_id")
    op.drop_index("ix_appointment_history_appointment_id", table_name="appointment_history")
    op.drop_table("appointment_history")
    op.drop_index("ix_appointment_batches_is_active", table_name="appointment_batches")
    op.drop_table("appointment_batches")

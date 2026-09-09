"""create nursing_records

Revision ID: 2f9a3c1b74d0
Revises: 1c4f8a9e02b7
Create Date: 2026-09-07

Additive only: one new table, ``nursing_records`` — a minimal vitals scaffold
(BP systolic/diastolic, temperature, notes) linked to an individual patient,
optionally to the appointment it was taken during, and to the recording user.
No existing table, column, row, or migration is touched.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2f9a3c1b74d0"
down_revision = "1c4f8a9e02b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nursing_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id"), nullable=True),
        sa.Column("recorded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("blood_pressure_systolic", sa.Integer(), nullable=True),
        sa.Column("blood_pressure_diastolic", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("corrects_record_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nursing_records.id"), nullable=True),
        sa.Column("correction_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_nursing_records_patient_id", "nursing_records", ["patient_id"])
    op.create_index("ix_nursing_records_appointment_id", "nursing_records", ["appointment_id"])
    op.create_index("ix_nursing_records_recorded_at", "nursing_records", ["recorded_at"])


def downgrade() -> None:
    op.drop_table("nursing_records")

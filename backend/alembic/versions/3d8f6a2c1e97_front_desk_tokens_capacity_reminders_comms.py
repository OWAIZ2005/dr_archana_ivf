"""Front desk phase 2: appointment tokens/notes, batch capacity limits,
reminders, and a patient-contact (communications) log.

Additive only; no existing table/column touched except two new nullable
columns on appointments and one new nullable column on
appointment_batches.

Revision ID: 3d8f6a2c1e97
Revises: 9a3f7c1e8b42
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "3d8f6a2c1e97"
down_revision = "9a3f7c1e8b42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("token_number", sa.Integer(), nullable=True))
    op.add_column("appointment_batches", sa.Column("capacity", sa.Integer(), nullable=True))

    op.create_table(
        "reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id"), nullable=True),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "COMPLETED", "CANCELLED", name="reminderstatus"), nullable=False, server_default="PENDING"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("completed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reminders_patient_id", "reminders", ["patient_id"])
    op.create_index("ix_reminders_appointment_id", "reminders", ["appointment_id"])
    op.create_index("ix_reminders_due_at", "reminders", ["due_at"])
    op.create_index("ix_reminders_status", "reminders", ["status"])

    op.create_table(
        "patient_communications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id"), nullable=True),
        sa.Column("channel", sa.Enum("CALL", "EMAIL", name="communicationchannel"), nullable=False),
        sa.Column("outcome", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("contacted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_patient_communications_patient_id", "patient_communications", ["patient_id"])
    op.create_index("ix_patient_communications_appointment_id", "patient_communications", ["appointment_id"])


def downgrade() -> None:
    op.drop_index("ix_patient_communications_appointment_id", table_name="patient_communications")
    op.drop_index("ix_patient_communications_patient_id", table_name="patient_communications")
    op.drop_table("patient_communications")
    sa.Enum(name="communicationchannel").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_reminders_status", table_name="reminders")
    op.drop_index("ix_reminders_due_at", table_name="reminders")
    op.drop_index("ix_reminders_appointment_id", table_name="reminders")
    op.drop_index("ix_reminders_patient_id", table_name="reminders")
    op.drop_table("reminders")
    sa.Enum(name="reminderstatus").drop(op.get_bind(), checkfirst=True)

    op.drop_column("appointment_batches", "capacity")
    op.drop_column("appointments", "token_number")
    op.drop_column("appointments", "notes")

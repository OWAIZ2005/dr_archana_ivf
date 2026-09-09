"""trigger injection, NPO windows, and message-log event/idempotency columns

Revision ID: 1c4f8a9e02b7
Revises: 0b7e1a4c9d21
Create Date: 2026-09-04

Additive:
  * new tables ``trigger_injections`` and ``npo_windows`` (hospital-side
    clinical events that drive staff notifications),
  * new ``trigger_status`` enum,
  * ``message_logs`` gains ``provider``, ``event_type``, ``event_id``,
    ``attempt``, ``dedupe_key`` (UNIQUE) + an ``(event_type, event_id)`` index,
    and ``patient_id`` becomes nullable (internal notifications have no patient
    recipient).

No data is dropped or rewritten. ``message_logs`` had no rows in the demo DB;
the ``patient_id`` NOT NULL -> NULL relaxation cannot fail on existing data.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "1c4f8a9e02b7"
down_revision = "0b7e1a4c9d21"
branch_labels = None
depends_on = None

trigger_status = postgresql.ENUM(
    "planned", "confirmed", "overdue", name="trigger_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    trigger_status.create(bind, checkfirst=True)

    # ---- message_logs: event linkage + idempotency + nullable patient ----
    op.alter_column("message_logs", "patient_id", existing_type=postgresql.UUID(), nullable=True)
    op.add_column("message_logs", sa.Column("provider", sa.String(length=32), nullable=True))
    op.add_column("message_logs", sa.Column("event_type", sa.String(length=48), nullable=True))
    op.add_column("message_logs", sa.Column("event_id", sa.String(length=64), nullable=True))
    op.add_column(
        "message_logs",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("message_logs", sa.Column("dedupe_key", sa.String(length=128), nullable=True))
    op.create_unique_constraint("uq_message_logs_dedupe_key", "message_logs", ["dedupe_key"])
    op.create_index("ix_message_logs_event", "message_logs", ["event_type", "event_id"])
    # server_default was only needed to backfill the (empty) table; the model
    # supplies the default from here on.
    op.alter_column("message_logs", "attempt", server_default=None)

    # ---- trigger_injections ----
    op.create_table(
        "trigger_injections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ivf_cycles.id"), nullable=False),
        sa.Column("medicine", sa.String(length=128), nullable=False),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", trigger_status, nullable=False, server_default="planned"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reminders_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_trigger_injections_cycle_id", "trigger_injections", ["cycle_id"])
    op.create_index("ix_trigger_injections_planned_at", "trigger_injections", ["planned_at"])
    op.create_index("ix_trigger_injections_status", "trigger_injections", ["status"])

    # ---- npo_windows ----
    op.create_table(
        "npo_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ivf_cycles.id"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_npo_windows_cycle_id", "npo_windows", ["cycle_id"])
    op.create_index("ix_npo_windows_start_at", "npo_windows", ["start_at"])


def downgrade() -> None:
    op.drop_table("npo_windows")
    op.drop_table("trigger_injections")
    trigger_status.drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_message_logs_event", table_name="message_logs")
    op.drop_constraint("uq_message_logs_dedupe_key", "message_logs", type_="unique")
    op.drop_column("message_logs", "dedupe_key")
    op.drop_column("message_logs", "attempt")
    op.drop_column("message_logs", "event_id")
    op.drop_column("message_logs", "event_type")
    op.drop_column("message_logs", "provider")
    op.alter_column("message_logs", "patient_id", existing_type=postgresql.UUID(), nullable=False)

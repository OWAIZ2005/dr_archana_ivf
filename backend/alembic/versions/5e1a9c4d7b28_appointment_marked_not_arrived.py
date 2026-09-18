"""Front desk: soft "Not Arrived" flag with a timestamp, distinct from the
terminal NO_SHOW status — lets the UI show a yellow countdown and only
nudge staff toward rescheduling after a grace period, instead of forcing
an immediate final no-show decision.

Additive only; one new nullable column.

Revision ID: 5e1a9c4d7b28
Revises: 3d8f6a2c1e97
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa

revision = "5e1a9c4d7b28"
down_revision = "3d8f6a2c1e97"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("marked_not_arrived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "marked_not_arrived_at")

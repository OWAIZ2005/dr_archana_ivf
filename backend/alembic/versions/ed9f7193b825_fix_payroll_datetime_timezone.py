"""fix_payroll_datetime_timezone

Revision ID: ed9f7193b825
Revises: e1ff5060435d
Create Date: 2026-09-29 16:16:06.699591

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ed9f7193b825'
down_revision: Union[str, None] = 'e1ff5060435d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # payroll_records.calculated_at/approved_at/paid_at were created as
    # TIMESTAMP WITHOUT TIME ZONE (missing timezone=True on the model in
    # the previous migration) — every other datetime in this app is
    # tz-aware, and calculate_payroll() passes a tz-aware datetime,
    # which asyncpg refuses to insert into a naive column.
    for col in ("calculated_at", "approved_at", "paid_at"):
        op.alter_column('payroll_records', col, type_=sa.DateTime(timezone=True), existing_nullable=True)


def downgrade() -> None:
    for col in ("calculated_at", "approved_at", "paid_at"):
        op.alter_column('payroll_records', col, type_=sa.DateTime(timezone=False), existing_nullable=True)

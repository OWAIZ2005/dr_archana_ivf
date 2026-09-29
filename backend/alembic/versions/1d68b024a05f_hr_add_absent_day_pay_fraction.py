"""hr add absent day pay fraction

Revision ID: 1d68b024a05f
Revises: 976661d6006e
Create Date: 2026-09-29 17:28:57.324248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1d68b024a05f'
down_revision: Union[str, None] = '976661d6006e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hr_settings",
        sa.Column("absent_day_pay_fraction", sa.Numeric(3, 2), nullable=False, server_default="0.00"),
    )


def downgrade() -> None:
    op.drop_column("hr_settings", "absent_day_pay_fraction")

"""fix_payrollstatus_draft_enum_case

Revision ID: 976661d6006e
Revises: 1e83a3152036
Create Date: 2026-09-29 16:57:25.948241

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '976661d6006e'
down_revision: Union[str, None] = '1e83a3152036'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1e83a3152036 added 'draft' (lowercase) to the payrollstatus enum, but
    # SQLAlchemy's Enum() stores the Python enum MEMBER NAME by default,
    # not .value — every existing label in this type is uppercase
    # ('CALCULATED', 'APPROVED', 'PAID', matching the original
    # e1ff5060435d migration), so inserts of PayrollStatus.DRAFT ("draft"
    # in Python) actually need the uppercase Postgres label 'DRAFT'. The
    # stray lowercase 'draft' value is harmless and left in place —
    # Postgres cannot drop a single enum value without rebuilding the type.
    op.execute("ALTER TYPE payrollstatus ADD VALUE IF NOT EXISTS 'DRAFT'")


def downgrade() -> None:
    pass

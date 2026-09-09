"""add discharge_summary value to the report_job_type enum

Revision ID: 0b7e1a4c9d21
Revises: 094de4bcd5b1
Create Date: 2026-09-04

Additive only. The async report pipeline (``report_jobs``) gains a second
artifact type, ``discharge_summary``, alongside ``patient_summary``. This adds
one label to the existing ``report_job_type`` PostgreSQL enum - no table or
column is created or altered, and no row is touched.
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0b7e1a4c9d21"
down_revision = "094de4bcd5b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block, so
    # step outside Alembic's per-migration transaction. IF NOT EXISTS keeps the
    # migration idempotent.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE report_job_type ADD VALUE IF NOT EXISTS 'discharge_summary'"
        )


def downgrade() -> None:
    # PostgreSQL has no ``ALTER TYPE ... DROP VALUE``. An unused enum label is
    # inert; removing it would require recreating the type and rewriting every
    # dependent column, which is not worth doing for a reversible-in-name-only
    # step. Left as a no-op deliberately.
    pass

"""Vendor medicine catalogue — lets a pharmacist mark a medicine as
available/unavailable from a given vendor, independent of purchase history.

Additive only; no existing table/column touched.

Revision ID: 4f8b1e6a2c9d
Revises: 2e6f9b4c8a71
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "4f8b1e6a2c9d"
down_revision = "2e6f9b4c8a71"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendor_medicine_catalog",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.UniqueConstraint("vendor_id", "medicine_id", name="uq_vendor_medicine_catalog"),
    )
    op.create_index("ix_vendor_medicine_catalog_vendor_id", "vendor_medicine_catalog", ["vendor_id"])
    op.create_index("ix_vendor_medicine_catalog_medicine_id", "vendor_medicine_catalog", ["medicine_id"])


def downgrade() -> None:
    op.drop_index("ix_vendor_medicine_catalog_medicine_id", table_name="vendor_medicine_catalog")
    op.drop_index("ix_vendor_medicine_catalog_vendor_id", table_name="vendor_medicine_catalog")
    op.drop_table("vendor_medicine_catalog")

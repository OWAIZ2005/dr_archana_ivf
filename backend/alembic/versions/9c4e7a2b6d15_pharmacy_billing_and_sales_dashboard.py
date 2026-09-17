"""Pharmacy billing/sales-dashboard columns — payment method and discount
on PharmacySale, so a bill records how it was paid and what was knocked
off, the way the reference Sales Dashboard reports them.

Additive only. Postgres enum labels use the Python Enum's member NAMES
(uppercase) — the convention every Enum column in this schema follows
(see 8b2d3f0a1c47 for why lowercase labels break writes).

Revision ID: 9c4e7a2b6d15
Revises: 8b2d3f0a1c47
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa

revision = "9c4e7a2b6d15"
down_revision = "8b2d3f0a1c47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pharmacy_sales", sa.Column("discount_paise", sa.Integer(), nullable=False, server_default="0"))

    # `op.add_column` does not issue CREATE TYPE for a brand-new enum used
    # on an ALTER TABLE (only `create_table` auto-creates it) — create it
    # explicitly first, checkfirst so this migration stays idempotent.
    payment_method_enum = sa.Enum("CASH", "CARD", "CHEQUE", "ONLINE", name="paymentmethod_pharmacy")
    payment_method_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "pharmacy_sales",
        sa.Column("payment_method", payment_method_enum, nullable=False, server_default="CASH"),
    )


def downgrade() -> None:
    op.drop_column("pharmacy_sales", "payment_method")
    op.drop_column("pharmacy_sales", "discount_paise")
    op.execute("DROP TYPE IF EXISTS paymentmethod_pharmacy")

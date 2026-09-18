"""Pharmacy: per-sale-line discount and split payments across methods.

Additive: existing pharmacy_sale_lines rows get discount_percent=0 (no
behavior change for already-recorded sales). Every existing
pharmacy_sales row is backfilled with exactly one pharmacy_sale_payments
row (its current payment_method + total_amount_paise), so the frontend
can always read the payment breakdown from the new table uniformly,
whether or not the sale was split.

Revision ID: 7c2e9d4a1b63
Revises: 4f8b1e6a2c9d
Create Date: 2026-09-18
"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "7c2e9d4a1b63"
down_revision = "4f8b1e6a2c9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pharmacy_sale_lines",
        sa.Column("discount_percent", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "pharmacy_sale_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sale_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_sales.id"), nullable=False),
        sa.Column("payment_method", postgresql.ENUM(name="paymentmethod_pharmacy", create_type=False), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
    )
    op.create_index("ix_pharmacy_sale_payments_sale_id", "pharmacy_sale_payments", ["sale_id"])

    bind = op.get_bind()
    existing_sales = bind.execute(sa.text("SELECT id, payment_method, total_amount_paise FROM pharmacy_sales")).fetchall()
    if existing_sales:
        payments_table = sa.table(
            "pharmacy_sale_payments",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("sale_id", postgresql.UUID(as_uuid=True)),
            sa.column("payment_method", postgresql.ENUM(name="paymentmethod_pharmacy", create_type=False)),
            sa.column("amount_paise", sa.Integer()),
        )
        bind.execute(
            payments_table.insert(),
            [
                {"id": uuid.uuid4(), "sale_id": row.id, "payment_method": row.payment_method, "amount_paise": row.total_amount_paise}
                for row in existing_sales
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_pharmacy_sale_payments_sale_id", table_name="pharmacy_sale_payments")
    op.drop_table("pharmacy_sale_payments")
    op.drop_column("pharmacy_sale_lines", "discount_percent")

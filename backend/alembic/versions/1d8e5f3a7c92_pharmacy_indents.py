"""Pharmacy Indents — department/room requests, delivery, returns, and a
generic pharmacy stock-transaction ledger those two flows write to.

Additive only; no existing table/column touched.

Revision ID: 1d8e5f3a7c92
Revises: 9c4e7a2b6d15
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "1d8e5f3a7c92"
down_revision = "9c4e7a2b6d15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- generic stock ledger ------------------------------------------ #
    op.create_table(
        "pharmacy_stock_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicine_batches.id"), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum("INDENT_DELIVERY", "INDENT_RETURN", name="pharmacystocktransactiontype"),
            nullable=False,
        ),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("reference_type", sa.String(32), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("performed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pharmacy_stock_transactions_medicine_id", "pharmacy_stock_transactions", ["medicine_id"])
    op.create_index("ix_pharmacy_stock_transactions_batch_id", "pharmacy_stock_transactions", ["batch_id"])
    op.create_index("ix_pharmacy_stock_transactions_reference_id", "pharmacy_stock_transactions", ["reference_id"])

    # ---- indent_requests / items ---------------------------------------- #
    op.create_table(
        "indent_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("indent_number", sa.String(32), nullable=False, unique=True),
        sa.Column("department", sa.String(128), nullable=False),
        sa.Column("room", sa.String(128), nullable=True),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PARTIALLY_DELIVERED", "DELIVERED", "CANCELLED", "RETURNED", name="indentstatus"),
            nullable=False, server_default="PENDING",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_indent_requests_indent_number", "indent_requests", ["indent_number"])
    op.create_index("ix_indent_requests_department", "indent_requests", ["department"])
    op.create_index("ix_indent_requests_status", "indent_requests", ["status"])

    op.create_table(
        "indent_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("indent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("indent_requests.id"), nullable=False),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("delivered_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("returned_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(500), nullable=True),
    )
    op.create_index("ix_indent_items_indent_id", "indent_items", ["indent_id"])

    # ---- indent_deliveries / lines --------------------------------------- #
    op.create_table(
        "indent_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("indent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("indent_requests.id"), nullable=False),
        sa.Column("delivered_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
    )
    op.create_index("ix_indent_deliveries_indent_id", "indent_deliveries", ["indent_id"])

    op.create_table(
        "indent_delivery_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("indent_deliveries.id"), nullable=False),
        sa.Column("indent_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("indent_items.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicine_batches.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_index("ix_indent_delivery_lines_delivery_id", "indent_delivery_lines", ["delivery_id"])

    # ---- indent_returns / lines ------------------------------------------ #
    op.create_table(
        "indent_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("indent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("indent_requests.id"), nullable=False),
        sa.Column("processed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
    )
    op.create_index("ix_indent_returns_indent_id", "indent_returns", ["indent_id"])

    op.create_table(
        "indent_return_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("return_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("indent_returns.id"), nullable=False),
        sa.Column("indent_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("indent_items.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicine_batches.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_index("ix_indent_return_lines_return_id", "indent_return_lines", ["return_id"])


def downgrade() -> None:
    op.drop_table("indent_return_lines")
    op.drop_table("indent_returns")
    op.drop_table("indent_delivery_lines")
    op.drop_table("indent_deliveries")
    op.drop_table("indent_items")
    op.drop_table("indent_requests")
    op.drop_table("pharmacy_stock_transactions")
    op.execute("DROP TYPE IF EXISTS indentstatus")
    op.execute("DROP TYPE IF EXISTS pharmacystocktransactiontype")

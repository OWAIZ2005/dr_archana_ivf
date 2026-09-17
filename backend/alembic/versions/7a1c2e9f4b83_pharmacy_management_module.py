"""Pharmacy Management module — attributes, vendor, purchase/GRN, sales
returns, stock adjustment; extends Medicine with catalogue/form fields.

Additive only: no existing column is dropped, renamed, or made non-nullable
in a way that breaks existing rows. `Medicine` gains nullable/defaulted
columns; the existing dispensing flow (Medicine/MedicineBatch/PharmacySale)
is untouched.

Revision ID: 7a1c2e9f4b83
Revises: 3d5e2af6c9b1
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "7a1c2e9f4b83"
down_revision = "3d5e2af6c9b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- vendors ----------------------------------------------------- #
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_code", sa.String(32), nullable=False, unique=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("gst_number", sa.String(16), nullable=True),
        sa.Column(
            "payment_type",
            # Postgres enum labels match the Python Enum's member NAMES
            # (uppercase), not their lowercase `.value` — the convention
            # every other Enum column in this schema follows (SQLAlchemy
            # persists `.name`; Pydantic serializes `.value` for the API).
            sa.Enum("CREDIT", "CASH", "CARD", "CHEQUE", "RTGS", "TRANSACTION", name="vendorpaymenttype"),
            nullable=False, server_default="CREDIT",
        ),
        sa.Column("credit_period_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purchase_limit_paise", sa.Integer(), nullable=True),
        sa.Column("days_to_deliver", sa.Integer(), nullable=True),
        sa.Column("bank_account_number", sa.String(32), nullable=True),
        sa.Column("bank_name", sa.String(128), nullable=True),
        sa.Column("ifsc_code", sa.String(16), nullable=True),
        sa.Column("contact_phone", sa.String(32), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_vendors_name", "vendors", ["name"])
    op.create_index("ix_vendors_account_code", "vendors", ["account_code"])
    op.create_index("ix_vendors_is_active", "vendors", ["is_active"])

    # ---- medicine_attributes ------------------------------------------ #
    op.create_table(
        "medicine_attributes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("attribute_type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("attribute_type", "name", name="uq_medicine_attribute_type_name"),
    )
    op.create_index("ix_medicine_attributes_attribute_type", "medicine_attributes", ["attribute_type"])
    op.create_index("ix_medicine_attributes_is_active", "medicine_attributes", ["is_active"])

    # ---- medicines: new columns ---------------------------------------- #
    op.add_column("medicines", sa.Column("purchase_tax_percent", sa.Integer(), nullable=False, server_default="12"))
    op.add_column("medicines", sa.Column("maximum_stock", sa.Integer(), nullable=True))
    op.add_column("medicines", sa.Column("medicine_type_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("medicines", sa.Column("item_code", sa.String(64), nullable=True))
    op.add_column("medicines", sa.Column("barcode", sa.String(64), nullable=True))
    op.add_column("medicines", sa.Column("rack_number", sa.String(32), nullable=True))
    op.add_column("medicines", sa.Column("mrp_paise", sa.Integer(), nullable=True))
    op.add_column("medicines", sa.Column("scheduled_drug", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("medicines", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_foreign_key(
        "fk_medicines_medicine_type_id", "medicines", "medicine_attributes", ["medicine_type_id"], ["id"]
    )
    op.create_index("ix_medicines_medicine_type_id", "medicines", ["medicine_type_id"])
    op.create_index("ix_medicines_is_active", "medicines", ["is_active"])
    op.create_unique_constraint("uq_medicines_barcode", "medicines", ["barcode"])

    # ---- pharmacy_purchases / pharmacy_purchase_lines ------------------- #
    op.create_table(
        "pharmacy_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("purchase_number", sa.String(32), nullable=False, unique=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("invoice_number", sa.String(64), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PARTIALLY_RECEIVED", "COMPLETED", "CANCELLED", name="purchasestatus"),
            nullable=False, server_default="PENDING",
        ),
        sa.Column("taxable_value_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cgst_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sgst_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_discount_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_value_paise", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("received_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pharmacy_purchases_purchase_number", "pharmacy_purchases", ["purchase_number"])
    op.create_index("ix_pharmacy_purchases_vendor_id", "pharmacy_purchases", ["vendor_id"])
    op.create_index("ix_pharmacy_purchases_status", "pharmacy_purchases", ["status"])

    op.create_table(
        "pharmacy_purchase_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_purchases.id"), nullable=False),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("batch_number", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("free_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purchase_rate_paise", sa.Integer(), nullable=False),
        sa.Column("selling_price_paise", sa.Integer(), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("hsn_code", sa.String(16), nullable=True),
        sa.Column("tax_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gross_amount_paise", sa.Integer(), nullable=False),
        sa.Column("total_value_paise", sa.Integer(), nullable=False),
    )
    op.create_index("ix_pharmacy_purchase_lines_purchase_id", "pharmacy_purchase_lines", ["purchase_id"])

    # ---- pharmacy_sale_returns / lines ---------------------------------- #
    op.create_table(
        "pharmacy_sale_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sale_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_sales.id"), nullable=False),
        sa.Column("processed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("total_refund_paise", sa.Integer(), nullable=False),
    )
    op.create_index("ix_pharmacy_sale_returns_sale_id", "pharmacy_sale_returns", ["sale_id"])

    op.create_table(
        "pharmacy_sale_return_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("return_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_sale_returns.id"), nullable=False),
        sa.Column("sale_line_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_sale_lines.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicine_batches.id"), nullable=False),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("refund_amount_paise", sa.Integer(), nullable=False),
    )
    op.create_index("ix_pharmacy_sale_return_lines_return_id", "pharmacy_sale_return_lines", ["return_id"])

    # ---- pharmacy_stock_adjustments ------------------------------------- #
    op.create_table(
        "pharmacy_stock_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicine_batches.id"), nullable=False),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("system_stock", sa.Integer(), nullable=False),
        sa.Column("physical_stock", sa.Integer(), nullable=False),
        sa.Column("difference", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("adjusted_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_pharmacy_stock_adjustments_batch_id", "pharmacy_stock_adjustments", ["batch_id"])


def downgrade() -> None:
    op.drop_table("pharmacy_stock_adjustments")
    op.drop_table("pharmacy_sale_return_lines")
    op.drop_table("pharmacy_sale_returns")
    op.drop_table("pharmacy_purchase_lines")
    op.drop_table("pharmacy_purchases")
    op.drop_constraint("uq_medicines_barcode", "medicines", type_="unique")
    op.drop_index("ix_medicines_is_active", table_name="medicines")
    op.drop_index("ix_medicines_medicine_type_id", table_name="medicines")
    op.drop_constraint("fk_medicines_medicine_type_id", "medicines", type_="foreignkey")
    for col in (
        "is_active", "scheduled_drug", "mrp_paise", "rack_number", "barcode",
        "item_code", "medicine_type_id", "maximum_stock", "purchase_tax_percent",
    ):
        op.drop_column("medicines", col)
    op.drop_table("medicine_attributes")
    op.drop_table("vendors")
    op.execute("DROP TYPE IF EXISTS purchasestatus")
    op.execute("DROP TYPE IF EXISTS vendorpaymenttype")

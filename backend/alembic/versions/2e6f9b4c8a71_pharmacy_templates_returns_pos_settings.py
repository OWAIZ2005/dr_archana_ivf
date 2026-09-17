"""Pharmacy Phases 2-6: Medicine Templates, Purchase Returns, Purchase
Orders, centralized Reports (query-only, no new tables), Pharmacy
Settings, and Indent Templates.

Additive only — no existing table/column touched, except two new labels
added to the existing pharmacystocktransactiontype enum (PURCHASE_RETURN,
PO_RECEIPT), via ADD VALUE (safe/idempotent, does not rewrite existing rows).

Revision ID: 2e6f9b4c8a71
Revises: 1d8e5f3a7c92
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2e6f9b4c8a71"
down_revision = "1d8e5f3a7c92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE pharmacystocktransactiontype ADD VALUE IF NOT EXISTS 'PURCHASE_RETURN'")
    op.execute("ALTER TYPE pharmacystocktransactiontype ADD VALUE IF NOT EXISTS 'PO_RECEIPT'")

    # ---- Medicine Templates (Phase 2) ---------------------------------- #
    op.create_table(
        "medicine_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("status", sa.Enum("ACTIVE", "INACTIVE", name="templatestatus"), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_medicine_templates_name", "medicine_templates", ["name"])
    op.create_index("ix_medicine_templates_status", "medicine_templates", ["status"])

    op.create_table(
        "template_medicine_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicine_templates.id"), nullable=False),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("default_quantity", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.UniqueConstraint("template_id", "medicine_id", name="uq_template_medicine"),
    )
    op.create_index("ix_template_medicine_mappings_template_id", "template_medicine_mappings", ["template_id"])

    # ---- Purchase Returns (Phase 3) ------------------------------------- #
    op.create_table(
        "pharmacy_purchase_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("return_number", sa.String(32), nullable=False, unique=True),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_purchases.id"), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_pharmacy_purchase_returns_return_number", "pharmacy_purchase_returns", ["return_number"])
    op.create_index("ix_pharmacy_purchase_returns_purchase_id", "pharmacy_purchase_returns", ["purchase_id"])
    op.create_index("ix_pharmacy_purchase_returns_vendor_id", "pharmacy_purchase_returns", ["vendor_id"])

    op.create_table(
        "pharmacy_purchase_return_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("return_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_purchase_returns.id"), nullable=False),
        sa.Column("purchase_line_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_purchase_lines.id"), nullable=False),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicine_batches.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("purchase_rate_paise", sa.Integer(), nullable=False),
        sa.Column("tax_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_paise", sa.Integer(), nullable=False),
    )
    op.create_index("ix_pharmacy_purchase_return_items_return_id", "pharmacy_purchase_return_items", ["return_id"])

    # ---- Purchase Orders (Phase 4) --------------------------------------- #
    op.create_table(
        "pharmacy_purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("po_number", sa.String(32), nullable=False, unique=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("po_date", sa.Date(), nullable=False),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("payment_terms", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_RECEIVED", "FULLY_RECEIVED", "CANCELLED", name="pharmacypurchaseorderstatus"),
            nullable=False, server_default="DRAFT",
        ),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_pharmacy_purchase_orders_po_number", "pharmacy_purchase_orders", ["po_number"])
    op.create_index("ix_pharmacy_purchase_orders_vendor_id", "pharmacy_purchase_orders", ["vendor_id"])
    op.create_index("ix_pharmacy_purchase_orders_status", "pharmacy_purchase_orders", ["status"])

    op.create_table(
        "pharmacy_purchase_order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("po_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pharmacy_purchase_orders.id"), nullable=False),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("ordered_quantity", sa.Integer(), nullable=False),
        sa.Column("received_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purchase_rate_paise", sa.Integer(), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tax_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expected_expiry", sa.Date(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
    )
    op.create_index("ix_pharmacy_purchase_order_items_po_id", "pharmacy_purchase_order_items", ["po_id"])

    # ---- Pharmacy Settings + Indent Templates (Phase 6) ------------------ #
    op.create_table(
        "pharmacy_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("pharmacy_name", sa.String(255), nullable=False, server_default="Dr. Archana IVF & Women Centre — Pharmacy"),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("gstin", sa.String(16), nullable=True),
        sa.Column("invoice_header", sa.String(500), nullable=True),
        sa.Column("invoice_footer", sa.String(500), nullable=True),
        sa.Column("show_gst", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_doctor", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_patient_details", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_batch", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_expiry", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_mrp", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_payment_info", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "indent_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("department", sa.String(128), nullable=True),
        sa.Column("room", sa.String(128), nullable=True),
        sa.Column("status", sa.Enum("ACTIVE", "INACTIVE", name="indenttemplatestatus"), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_indent_templates_name", "indent_templates", ["name"])
    op.create_index("ix_indent_templates_status", "indent_templates", ["status"])

    op.create_table(
        "indent_template_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("indent_templates.id"), nullable=False),
        sa.Column("medicine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("medicines.id"), nullable=False),
        sa.Column("default_quantity", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
    )
    op.create_index("ix_indent_template_items_template_id", "indent_template_items", ["template_id"])


def downgrade() -> None:
    op.drop_table("indent_template_items")
    op.drop_table("indent_templates")
    op.drop_table("pharmacy_settings")
    op.drop_table("pharmacy_purchase_order_items")
    op.drop_table("pharmacy_purchase_orders")
    op.drop_table("pharmacy_purchase_return_items")
    op.drop_table("pharmacy_purchase_returns")
    op.drop_table("template_medicine_mappings")
    op.drop_table("medicine_templates")
    op.execute("DROP TYPE IF EXISTS indenttemplatestatus")
    op.execute("DROP TYPE IF EXISTS pharmacypurchaseorderstatus")
    op.execute("DROP TYPE IF EXISTS templatestatus")
    # Postgres cannot DROP VALUE from an enum type; leaving the two added
    # labels in place on downgrade is the standard, safe approach.

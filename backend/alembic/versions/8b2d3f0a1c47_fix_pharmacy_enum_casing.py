"""Fix vendorpaymenttype/purchasestatus enum label casing.

The pharmacy migration (7a1c2e9f4b83) created these Postgres enum types
with lowercase labels ("credit", "pending", ...), but every other Enum
column in this schema stores the Python Enum's member NAME (uppercase) —
SQLAlchemy persists `.name`, not `.value`. That mismatch made every write
through `Vendor.payment_type` / `PharmacyPurchase.status` fail with
`InvalidTextRepresentationError`. Rebuilds both enum types with the
correct (uppercase) labels; `UPPER(...)` in the USING clause preserves
any rows already written under the broken lowercase type.

Revision ID: 8b2d3f0a1c47
Revises: 7a1c2e9f4b83
Create Date: 2026-09-15
"""
from alembic import op

revision = "8b2d3f0a1c47"
down_revision = "7a1c2e9f4b83"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE vendors ALTER COLUMN payment_type DROP DEFAULT")
    op.execute("ALTER TABLE vendors ALTER COLUMN payment_type TYPE varchar(32) USING UPPER(payment_type::text)")
    op.execute("DROP TYPE vendorpaymenttype")
    op.execute("CREATE TYPE vendorpaymenttype AS ENUM ('CREDIT', 'CASH', 'CARD', 'CHEQUE', 'RTGS', 'TRANSACTION')")
    op.execute("ALTER TABLE vendors ALTER COLUMN payment_type TYPE vendorpaymenttype USING payment_type::vendorpaymenttype")
    op.execute("ALTER TABLE vendors ALTER COLUMN payment_type SET DEFAULT 'CREDIT'")

    op.execute("ALTER TABLE pharmacy_purchases ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE pharmacy_purchases ALTER COLUMN status TYPE varchar(32) USING UPPER(status::text)")
    op.execute("DROP TYPE purchasestatus")
    op.execute("CREATE TYPE purchasestatus AS ENUM ('PENDING', 'PARTIALLY_RECEIVED', 'COMPLETED', 'CANCELLED')")
    op.execute("ALTER TABLE pharmacy_purchases ALTER COLUMN status TYPE purchasestatus USING status::purchasestatus")
    op.execute("ALTER TABLE pharmacy_purchases ALTER COLUMN status SET DEFAULT 'PENDING'")


def downgrade() -> None:
    op.execute("ALTER TABLE vendors ALTER COLUMN payment_type DROP DEFAULT")
    op.execute("ALTER TABLE vendors ALTER COLUMN payment_type TYPE varchar(32) USING LOWER(payment_type::text)")
    op.execute("DROP TYPE vendorpaymenttype")
    op.execute("CREATE TYPE vendorpaymenttype AS ENUM ('credit', 'cash', 'card', 'cheque', 'rtgs', 'transaction')")
    op.execute("ALTER TABLE vendors ALTER COLUMN payment_type TYPE vendorpaymenttype USING payment_type::vendorpaymenttype")
    op.execute("ALTER TABLE vendors ALTER COLUMN payment_type SET DEFAULT 'credit'")

    op.execute("ALTER TABLE pharmacy_purchases ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE pharmacy_purchases ALTER COLUMN status TYPE varchar(32) USING LOWER(status::text)")
    op.execute("DROP TYPE purchasestatus")
    op.execute("CREATE TYPE purchasestatus AS ENUM ('pending', 'partially_received', 'completed', 'cancelled')")
    op.execute("ALTER TABLE pharmacy_purchases ALTER COLUMN status TYPE purchasestatus USING status::purchasestatus")
    op.execute("ALTER TABLE pharmacy_purchases ALTER COLUMN status SET DEFAULT 'pending'")

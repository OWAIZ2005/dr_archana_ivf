"""asset & item tracking: location master + FK location columns + opaque QR token

Revision ID: 3d5e2af6c9b1
Revises: 2f9a3c1b74d0
Create Date: 2026-09-07

Additive only:
  * new ``locations`` table (venue master),
  * ``assets`` gains ``current_location_id`` (FK locations), ``qr_token``
    (opaque, unique, backfilled for existing rows), ``registered_by_id``,
  * ``asset_movements`` gains ``from_location_id`` / ``to_location_id``
    (FK locations).

The legacy free-text columns ``assets.current_location`` /
``asset_movements.from_location`` / ``asset_movements.to_location`` are KEPT and
continue to be written in sync. No table is dropped, no row is deleted.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "3d5e2af6c9b1"
down_revision = "2f9a3c1b74d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("building", sa.String(length=128), nullable=True),
        sa.Column("floor", sa.String(length=64), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("in_charge", sa.String(length=128), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_locations_name", "locations", ["name"])
    op.create_index("ix_locations_name", "locations", ["name"])
    op.create_index("ix_locations_is_active", "locations", ["is_active"])

    # ---- assets ----
    op.add_column("assets", sa.Column("current_location_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("assets", sa.Column("qr_token", sa.String(length=48), nullable=True))
    op.add_column("assets", sa.Column("registered_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_assets_current_location_id", "assets", "locations", ["current_location_id"], ["id"])
    op.create_foreign_key("fk_assets_registered_by_id", "assets", "users", ["registered_by_id"], ["id"])
    op.create_index("ix_assets_current_location_id", "assets", ["current_location_id"])

    # Backfill qr_token for any pre-existing asset rows, then enforce NOT NULL + UNIQUE.
    op.execute("UPDATE assets SET qr_token = replace(md5(random()::text || id::text), '-', '') WHERE qr_token IS NULL")
    op.alter_column("assets", "qr_token", existing_type=sa.String(length=48), nullable=False)
    op.create_unique_constraint("uq_assets_qr_token", "assets", ["qr_token"])
    op.create_index("ix_assets_qr_token", "assets", ["qr_token"])

    # ---- asset_movements ----
    op.add_column("asset_movements", sa.Column("from_location_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("asset_movements", sa.Column("to_location_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_asset_movements_from_location_id", "asset_movements", "locations", ["from_location_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_asset_movements_to_location_id", "asset_movements", "locations", ["to_location_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_asset_movements_to_location_id", "asset_movements", type_="foreignkey")
    op.drop_constraint("fk_asset_movements_from_location_id", "asset_movements", type_="foreignkey")
    op.drop_column("asset_movements", "to_location_id")
    op.drop_column("asset_movements", "from_location_id")

    op.drop_index("ix_assets_qr_token", table_name="assets")
    op.drop_constraint("uq_assets_qr_token", "assets", type_="unique")
    op.drop_index("ix_assets_current_location_id", table_name="assets")
    op.drop_constraint("fk_assets_registered_by_id", "assets", type_="foreignkey")
    op.drop_constraint("fk_assets_current_location_id", "assets", type_="foreignkey")
    op.drop_column("assets", "registered_by_id")
    op.drop_column("assets", "qr_token")
    op.drop_column("assets", "current_location_id")

    op.drop_index("ix_locations_is_active", table_name="locations")
    op.drop_index("ix_locations_name", table_name="locations")
    op.drop_constraint("uq_locations_name", "locations", type_="unique")
    op.drop_table("locations")

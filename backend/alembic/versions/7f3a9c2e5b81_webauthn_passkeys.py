"""Passkeys (WebAuthn / Face ID / Touch ID) — additive login option
alongside the existing password flow, never a replacement (see
app/webauthn/models.py for why). Two new tables: webauthn_credentials
(one row per registered authenticator, long-lived) and
webauthn_challenges (one row per in-flight registration/login ceremony,
short-lived — the challenge column is that row's own lookup key).

Additive only; no existing table is touched.

Revision ID: 7f3a9c2e5b81
Revises: 5e1a9c4d7b28
Create Date: 2026-09-19
"""
from alembic import op
import sqlalchemy as sa

revision = "7f3a9c2e5b81"
down_revision = "5e1a9c4d7b28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webauthn_credentials",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("credential_id", sa.String(length=512), nullable=False),
        sa.Column("public_key", sa.String(length=1024), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False),
        sa.Column("device_label", sa.String(length=255), nullable=True),
        sa.Column("aaguid", sa.String(length=64), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_id"),
    )
    op.create_index(op.f("ix_webauthn_credentials_user_id"), "webauthn_credentials", ["user_id"], unique=False)
    op.create_index(op.f("ix_webauthn_credentials_credential_id"), "webauthn_credentials", ["credential_id"], unique=False)

    op.create_table(
        "webauthn_challenges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("challenge", sa.String(length=256), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge"),
    )
    op.create_index(op.f("ix_webauthn_challenges_challenge"), "webauthn_challenges", ["challenge"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_webauthn_challenges_challenge"), table_name="webauthn_challenges")
    op.drop_table("webauthn_challenges")
    op.drop_index(op.f("ix_webauthn_credentials_credential_id"), table_name="webauthn_credentials")
    op.drop_index(op.f("ix_webauthn_credentials_user_id"), table_name="webauthn_credentials")
    op.drop_table("webauthn_credentials")

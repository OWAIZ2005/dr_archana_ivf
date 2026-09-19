"""
Passkeys (WebAuthn / Face ID / Touch ID) — additive to the password login
in app/auth, never a replacement. A shared front-desk iPad can't reliably
enroll every receptionist's face (iOS supports at most one "Alternate
Appearance"), so this is a fast option for people who mostly use their own
device, plus a quick-unlock after an idle timeout on shared ones. Password
always stays the fallback that works for everyone.

Two tables:
  - WebAuthnCredential: one row per registered authenticator, long-lived.
  - WebAuthnChallenge: one row per in-flight registration/login ceremony,
    short-lived (see Settings.WEBAUTHN_CHALLENGE_TTL_SECONDS). The
    challenge itself is the natural lookup key (a fresh cryptographically
    random 32+ byte value per ceremony, per generate_challenge()) — no
    separate opaque session id needs to round-trip to the frontend and
    back. Consumed (deleted) on first successful lookup, so a captured
    verify request can't be replayed even within its TTL.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class WebAuthnCredential(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "webauthn_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # The WebAuthn credential ID and public key, both base64url-encoded —
    # this table never stores raw bytes, matching how every other opaque
    # binary identifier in this codebase (e.g. patients.storage_object_key)
    # is kept as a plain indexable string rather than a BYTEA column.
    credential_id: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    public_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # e.g. "iPad — Front Desk", set by the person registering it — same
    # free-text convention as Session.device_label in app/auth/models.py,
    # since this is the same idea (which device this credential lives on).
    device_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    aaguid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebAuthnChallenge(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "webauthn_challenges"

    purpose: Mapped[str] = mapped_column(String(32), nullable=False)  # "registration" | "authentication"
    # Known for registration (the caller is already authenticated and is
    # registering a credential for themselves); null for authentication —
    # at that point we don't yet know who's signing in, that's exactly
    # what the ceremony establishes.
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    challenge: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

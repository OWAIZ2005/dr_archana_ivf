"""
Passkey registration and login ceremonies.

Login here deliberately reuses app.auth.service._issue_token_pair and
creates a real app.auth.models.Session row — a passkey sign-in produces
the exact same session/token shape a password sign-in does, so every
other part of this backend (idle timeout, "log out everywhere", refresh
rotation) keeps working unmodified regardless of which login method was
used. There is no separate "passkey session" concept.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.audit.service import record_audit_event
from app.auth.models import Session as AuthSession
from app.auth.service import _issue_token_pair
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, NotFoundError
from app.users.models import User
from app.webauthn.models import WebAuthnChallenge, WebAuthnCredential

settings = get_settings()


async def _consume_challenge(
    session: AsyncSession, *, purpose: str, challenge: str, user_id: uuid.UUID | None
) -> WebAuthnChallenge | None:
    """Single-use: deletes the row on the first successful lookup, so a
    captured verify request can't be replayed even inside its TTL."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(WebAuthnChallenge).where(
            WebAuthnChallenge.purpose == purpose,
            WebAuthnChallenge.challenge == challenge,
            WebAuthnChallenge.expires_at > now,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    if user_id is not None and row.user_id != user_id:
        return None
    await session.delete(row)
    await session.flush()
    return row


async def _store_challenge(
    session: AsyncSession, *, purpose: str, challenge_bytes: bytes, user_id: uuid.UUID | None
) -> str:
    challenge_b64 = bytes_to_base64url(challenge_bytes)
    row = WebAuthnChallenge(
        purpose=purpose,
        user_id=user_id,
        challenge=challenge_b64,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.WEBAUTHN_CHALLENGE_TTL_SECONDS),
    )
    session.add(row)
    await session.flush()
    return challenge_b64


# ---------------------------------------------------------------------------
# Registration — self-service, the caller is already authenticated
# ---------------------------------------------------------------------------

async def begin_registration(session: AsyncSession, *, user: User) -> dict:
    existing = await session.execute(
        select(WebAuthnCredential.credential_id).where(WebAuthnCredential.user_id == user.id)
    )
    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred_id)) for cred_id in existing.scalars().all()
    ]

    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=user.id.bytes,
        user_name=user.email,
        user_display_name=user.full_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            # PLATFORM, not cross-platform: this requests Face ID/Touch ID
            # specifically, not a roaming security key — matching the
            # product decision that this is a device-bound convenience
            # login, not a general FIDO2 key management feature.
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=exclude_credentials or None,
    )
    await _store_challenge(session, purpose="registration", challenge_bytes=options.challenge, user_id=user.id)
    return options_to_json(options)


async def verify_registration(
    session: AsyncSession, *, user: User, credential: dict, challenge: str, device_label: str | None
) -> WebAuthnCredential:
    row = await _consume_challenge(session, purpose="registration", challenge=challenge, user_id=user.id)
    if row is None:
        raise AuthenticationError("This registration request has expired — try again.", error_code="challenge_expired")

    verification = verify_registration_response(
        credential=credential,
        expected_challenge=base64url_to_bytes(challenge),
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.WEBAUTHN_ORIGIN,
        require_user_verification=True,
    )

    cred = WebAuthnCredential(
        user_id=user.id,
        credential_id=bytes_to_base64url(verification.credential_id),
        public_key=bytes_to_base64url(verification.credential_public_key),
        sign_count=verification.sign_count,
        device_label=device_label,
        aaguid=verification.aaguid,
    )
    session.add(cred)
    await record_audit_event(
        session, actor_id=user.id, actor_role=user.role.code,
        action="auth.passkey_registered", entity_type="WebAuthnCredential", entity_id=None,
        after_state={"device_label": device_label},
    )
    await session.flush()
    return cred


async def list_passkeys(session: AsyncSession, *, user: User) -> list[WebAuthnCredential]:
    result = await session.execute(
        select(WebAuthnCredential)
        .where(WebAuthnCredential.user_id == user.id)
        .order_by(WebAuthnCredential.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_passkey(session: AsyncSession, *, user: User, credential_id: uuid.UUID) -> None:
    cred = await session.get(WebAuthnCredential, credential_id)
    if cred is None or cred.user_id != user.id:
        raise NotFoundError("Passkey not found.")
    await session.delete(cred)
    await record_audit_event(
        session, actor_id=user.id, actor_role=user.role.code,
        action="auth.passkey_revoked", entity_type="WebAuthnCredential", entity_id=str(credential_id),
    )


# ---------------------------------------------------------------------------
# Login — the caller is NOT authenticated yet; that's what this establishes
# ---------------------------------------------------------------------------

async def begin_authentication(session: AsyncSession) -> dict:
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        user_verification=UserVerificationRequirement.REQUIRED,
        # No allow_credentials list: this is a discoverable-credential
        # (resident key) flow — the OS picks from whichever passkeys for
        # this site are on the device, rather than us needing to know who
        # is signing in before they've told us.
    )
    await _store_challenge(session, purpose="authentication", challenge_bytes=options.challenge, user_id=None)
    return options_to_json(options)


async def verify_authentication(
    session: AsyncSession, *, credential: dict, challenge: str, ip_address: str | None, user_agent: str | None
) -> tuple[str, str, User]:
    row = await _consume_challenge(session, purpose="authentication", challenge=challenge, user_id=None)
    if row is None:
        raise AuthenticationError("This sign-in request has expired — try again.", error_code="challenge_expired")

    raw_id = credential.get("rawId") or credential.get("id")
    if not raw_id:
        raise AuthenticationError("Malformed passkey response.")

    result = await session.execute(select(WebAuthnCredential).where(WebAuthnCredential.credential_id == raw_id))
    stored = result.scalar_one_or_none()
    if stored is None:
        raise AuthenticationError("This passkey is not registered for any account here.")

    verification = verify_authentication_response(
        credential=credential,
        expected_challenge=base64url_to_bytes(challenge),
        expected_rp_id=settings.WEBAUTHN_RP_ID,
        expected_origin=settings.WEBAUTHN_ORIGIN,
        credential_public_key=base64url_to_bytes(stored.public_key),
        credential_current_sign_count=stored.sign_count,
        require_user_verification=True,
    )

    now = datetime.now(timezone.utc)
    stored.sign_count = verification.new_sign_count
    stored.last_used_at = now

    user = await session.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("This account has been deactivated.")

    auth_session = AuthSession(
        user_id=user.id,
        device_label=stored.device_label or "Passkey sign-in",
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=now + timedelta(hours=settings.ABSOLUTE_SESSION_LIFETIME_HOURS),
        last_active_at=now,
    )
    session.add(auth_session)
    await session.flush()

    access, refresh = await _issue_token_pair(session, user=user, auth_session=auth_session)

    await record_audit_event(
        session, actor_id=user.id, actor_role=user.role.code,
        action="auth.passkey_login_success", entity_type="Session", entity_id=str(auth_session.id),
        source_ip=ip_address, session_id=auth_session.id,
    )
    return access, refresh, user

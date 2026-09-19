"""
Passkey (WebAuthn) tests.

Full registration/login ceremonies need a real authenticator's private key
signing real challenges — there is no lightweight way to fake that inside
this test suite without embedding a software CTAP2 authenticator, which is
out of scope here. What IS tested is everything this module is actually
responsible for getting right on its own: the options endpoints return a
spec-shaped, platform-only, user-verification-required request; challenges
are genuinely single-use; and a passkey can only ever be revoked by the
account that owns it. The underlying signature verification itself is
delegated to, and already covered by, the `webauthn` package's own test
suite — re-testing that here would just be testing someone else's library.
"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.users.models import User
from app.webauthn import service
from app.webauthn.models import WebAuthnCredential


async def test_list_passkeys_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/auth/passkeys")
    assert resp.status_code == 401


async def test_registration_options_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/auth/passkeys/register/options")
    assert resp.status_code == 401


async def test_registration_options_request_platform_and_user_verification(client: AsyncClient, auth_headers: dict):
    """The two properties that make this "Face ID, not a security key" and
    "biometric confirmed, not just device presence" — if either regresses,
    the browser starts offering the wrong authenticator type."""
    resp = await client.post("/api/v1/auth/passkeys/register/options", headers=auth_headers)
    assert resp.status_code == 200
    options = resp.json()["options"]
    assert options["authenticatorSelection"]["authenticatorAttachment"] == "platform"
    assert options["authenticatorSelection"]["userVerification"] == "required"
    assert options["rp"]["id"] == "localhost"


async def test_login_options_is_unauthenticated(client: AsyncClient):
    """The whole point: this must work before anyone is signed in — it's
    what establishes who's signing in, not a route that assumes it."""
    resp = await client.post("/api/v1/auth/passkeys/login/options")
    assert resp.status_code == 200
    options = resp.json()["options"]
    assert options["userVerification"] == "required"
    assert options["allowCredentials"] == []  # discoverable-credential flow, not a pre-known list


async def test_registration_options_excludes_already_registered_credentials(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, doctor_user: User
):
    existing = WebAuthnCredential(
        user_id=doctor_user.id,
        credential_id="ZoIKP1JQvKdrYj1bTUPJ2eTUsbLeFkv-X5xJQNr4k6s",
        public_key="dGVzdC1wdWJsaWMta2V5",
        sign_count=0,
    )
    db_session.add(existing)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/passkeys/register/options", headers=auth_headers)
    assert resp.status_code == 200
    exclude_ids = [c["id"] for c in resp.json()["options"]["excludeCredentials"]]
    assert existing.credential_id in exclude_ids


async def test_challenge_is_single_use(db_session: AsyncSession, doctor_user: User):
    challenge = await service._store_challenge(
        db_session, purpose="registration", challenge_bytes=b"0123456789abcdef", user_id=doctor_user.id
    )
    first = await service._consume_challenge(
        db_session, purpose="registration", challenge=challenge, user_id=doctor_user.id
    )
    assert first is not None

    replay = await service._consume_challenge(
        db_session, purpose="registration", challenge=challenge, user_id=doctor_user.id
    )
    assert replay is None, "A challenge must not be usable a second time — that's the entire anti-replay point of it."


async def test_expired_challenge_is_rejected(db_session: AsyncSession, doctor_user: User):
    from app.webauthn.models import WebAuthnChallenge

    expired = WebAuthnChallenge(
        purpose="registration",
        user_id=doctor_user.id,
        challenge="already-expired-challenge-value",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    db_session.add(expired)
    await db_session.commit()

    row = await service._consume_challenge(
        db_session, purpose="registration", challenge="already-expired-challenge-value", user_id=doctor_user.id
    )
    assert row is None


async def test_verify_registration_rejects_unknown_challenge(db_session: AsyncSession, doctor_user: User):
    with pytest.raises(AuthenticationError):
        await service.verify_registration(
            db_session, user=doctor_user, credential={}, challenge="never-issued", device_label=None
        )


async def test_revoke_passkey_requires_ownership(
    client: AsyncClient, db_session: AsyncSession, doctor_user: User, admin_user: User
):
    """The admin's own passkey must be untouchable through the doctor's
    session — this is a self-service endpoint, not an admin one, and
    "self" must mean exactly one account."""
    others_cred = WebAuthnCredential(
        user_id=admin_user.id,
        credential_id="not-the-doctors-credential",
        public_key="dGVzdA==",
        sign_count=0,
    )
    db_session.add(others_cred)
    await db_session.commit()

    login = await client.post("/api/v1/auth/login", json={"email": "doctor@example.com", "password": "TestPass123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.delete(f"/api/v1/auth/passkeys/{others_cred.id}", headers=headers)
    assert resp.status_code == 404


async def test_revoke_own_passkey_succeeds(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, doctor_user: User):
    own_cred = WebAuthnCredential(
        user_id=doctor_user.id,
        credential_id="the-doctors-own-credential",
        public_key="dGVzdA==",
        sign_count=0,
    )
    db_session.add(own_cred)
    await db_session.commit()

    resp = await client.delete(f"/api/v1/auth/passkeys/{own_cred.id}", headers=auth_headers)
    assert resp.status_code == 204

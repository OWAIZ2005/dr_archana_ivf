import json

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.router import _set_refresh_cookie
from app.auth.schemas import TokenResponse
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.users.models import User
from app.webauthn import service
from app.webauthn.schemas import (
    AuthenticationOptionsOut,
    AuthenticationVerifyRequest,
    PasskeyOut,
    RegistrationOptionsOut,
    RegistrationVerifyRequest,
)

router = APIRouter(prefix="/auth/passkeys", tags=["passkeys"])
settings = get_settings()


# ---- Self-service management — same "no extra permission code" pattern as
# POST /auth/change-password: registering/revoking your OWN passkey needs
# nothing beyond being signed in, same as changing your own password does. ----

@router.get("", response_model=list[PasskeyOut])
async def list_my_passkeys(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PasskeyOut]:
    return await service.list_passkeys(session, user=user)


@router.post("/register/options", response_model=RegistrationOptionsOut)
async def registration_options(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RegistrationOptionsOut:
    options_json = await service.begin_registration(session, user=user)
    return RegistrationOptionsOut(options=json.loads(options_json))


@router.post("/register/verify", response_model=PasskeyOut, status_code=201)
async def registration_verify(
    body: RegistrationVerifyRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PasskeyOut:
    cred = await service.verify_registration(
        session, user=user, credential=body.credential, challenge=body.challenge, device_label=body.device_label
    )
    return PasskeyOut.model_validate(cred)


@router.delete("/{credential_id}", status_code=204)
async def revoke_passkey(
    credential_id: str,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    await service.revoke_passkey(session, user=user, credential_id=credential_id)


# ---- Login — unauthenticated, same as POST /auth/login itself ----

@router.post("/login/options", response_model=AuthenticationOptionsOut)
async def login_options(session: AsyncSession = Depends(get_db)) -> AuthenticationOptionsOut:
    options_json = await service.begin_authentication(session)
    return AuthenticationOptionsOut(options=json.loads(options_json))


@router.post("/login/verify", response_model=TokenResponse)
async def login_verify(
    body: AuthenticationVerifyRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    access, refresh, user = await service.verify_authentication(
        session,
        credential=body.credential,
        challenge=body.challenge,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

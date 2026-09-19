from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import AuthenticationError
from app.core.security import hash_password, validate_password_strength, verify_password
from app.users.models import User
from app.users.schemas import UserSummary

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# httpOnly refresh-token cookie; the access token is returned in the body for
# the frontend to hold in memory only (never localStorage — see
# docs/security/authentication.md).
#
# Same-origin deployments (SPA and API behind one host, as with the nginx setup
# in docker-compose) keep SameSite=Strict. When the API is served from a
# different origin than the SPA — e.g. the SPA on Vercel and the API behind a
# tunnel — a Strict cookie is never sent on the cross-site /auth/refresh call,
# so any non-local environment uses SameSite=None, which the browser only
# accepts together with Secure. `allow_credentials=True` plus an explicit
# origin list in CORS_ORIGINS (never "*") keep this safe.
REFRESH_COOKIE = "hmis_refresh"


def _set_refresh_cookie(response: Response, token: str) -> None:
    is_local = settings.ENVIRONMENT == "local"
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=not is_local,
        samesite="strict" if is_local else "none",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/v1/auth",
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    access, refresh, user = await auth_service.login(
        session,
        email=body.email,
        password=body.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        device_label=body.device_label,
    )
    _set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    raw_token = body.refresh_token if body else request.cookies.get(REFRESH_COOKIE)
    if not raw_token:
        raise AuthenticationError("No refresh token provided.")

    access, refresh_token = await auth_service.refresh_tokens(
        session,
        raw_refresh_token=raw_token,
        ip_address=request.client.host if request.client else None,
    )
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh_token,
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    await auth_service.logout(session, session_id=request.state.session_id, actor_id=user.id)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")


@router.get("/me", response_model=UserSummary)
async def me(user: User = Depends(get_current_user)) -> UserSummary:
    return UserSummary(
        id=user.id,
        employee_code=user.employee_code,
        full_name=user.full_name,
        email=user.email,
        department=user.department,
        is_active=user.is_active,
        role_code=user.role.code,
        permissions=sorted({p.code for p in user.role.permissions}),
        idle_timeout_minutes=settings.IDLE_TIMEOUT_MINUTES,
    )


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise AuthenticationError("Current password is incorrect.")

    errors = validate_password_strength(body.new_password)
    if errors:
        raise AuthenticationError("; ".join(errors), error_code="weak_password")

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    from datetime import datetime, timezone
    user.password_changed_at = datetime.now(timezone.utc)

    await auth_service.revoke_all_sessions_for_user(
        session, user_id=user.id, reason="password_changed"
    )

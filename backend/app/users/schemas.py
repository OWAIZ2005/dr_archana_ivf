import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_code: str
    full_name: str
    email: EmailStr
    department: str | None
    is_active: bool
    role_code: str
    # Flat list of permission codes the user's role grants. Populated by
    # GET /auth/me so the frontend can hide (never authorize — the backend
    # still enforces) capabilities the user lacks, e.g. the asset "Move"
    # action. Other UserSummary producers leave it empty.
    permissions: list[str] = []
    # Settings.IDLE_TIMEOUT_MINUTES, echoed back so the frontend's idle-lock
    # overlay (lib/idleLock.tsx) can match the server's own idle-timeout
    # window instead of hardcoding a guess that could silently drift from
    # it. Same "populated by GET /auth/me only" convention as permissions
    # above — this is app-wide config, not really a per-user field, but
    # /auth/me is the one place the frontend already fetches on every
    # login/session-restore, so it's the natural carrier.
    idle_timeout_minutes: int | None = None


class UserCreate(BaseModel):
    employee_code: str
    full_name: str
    email: EmailStr
    phone: str | None = None
    department: str | None = None
    role_id: uuid.UUID
    temporary_password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    department: str | None = None
    role_id: uuid.UUID | None = None
    is_active: bool | None = None

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

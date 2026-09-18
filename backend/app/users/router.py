from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_any_permission, require_permission
from app.users import service
from app.users.models import User
from app.users.schemas import UserCreate, UserSummary, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserSummary])
async def list_users(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("admin.manage_users")),
) -> list[UserSummary]:
    users = await service.list_users(session)
    return [
        UserSummary(
            id=u.id, employee_code=u.employee_code, full_name=u.full_name, email=u.email,
            department=u.department, is_active=u.is_active, role_code=u.role.code,
        )
        for u in users
    ]


@router.get("/doctors", response_model=list[UserSummary])
async def list_doctors(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_any_permission("appointments.read", "pharmacy.dispense")),
) -> list[UserSummary]:
    """Lightweight staff-picker for the appointment book and other
    scheduling UIs — deliberately gated behind appointments.read/
    pharmacy.dispense rather than admin.manage_users, since front-desk,
    clinical and pharmacy roles all need this list (pharmacy's New Bill
    records an optional prescribing doctor) but should never see the full
    user-management endpoint."""
    users = await service.list_users_by_role_code(session, "doctor")
    return [
        UserSummary(
            id=u.id, employee_code=u.employee_code, full_name=u.full_name, email=u.email,
            department=u.department, is_active=u.is_active, role_code=u.role.code,
        )
        for u in users
    ]


@router.get("/embryologists", response_model=list[UserSummary])
async def list_embryologists(
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("embryology.read")),
) -> list[UserSummary]:
    """Same rationale as /users/doctors — the transfer workflow needs to
    pick an embryologist without granting admin.manage_users."""
    users = await service.list_users_by_role_code(session, "embryologist")
    return [
        UserSummary(
            id=u.id, employee_code=u.employee_code, full_name=u.full_name, email=u.email,
            department=u.department, is_active=u.is_active, role_code=u.role.code,
        )
        for u in users
    ]


@router.post("", response_model=UserSummary, status_code=201)
async def create_user(
    body: UserCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("admin.manage_users")),
) -> UserSummary:
    user = await service.create_user(session, body, actor_id=current.id, actor_role=current.role.code)
    return UserSummary(
        id=user.id, employee_code=user.employee_code, full_name=user.full_name, email=user.email,
        department=user.department, is_active=user.is_active, role_code=user.role.code,
    )


@router.patch("/{user_id}", response_model=UserSummary)
async def update_user(
    user_id: str,
    body: UserUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("admin.manage_users")),
) -> UserSummary:
    user = await service.update_user(session, user_id, body, actor_id=current.id, actor_role=current.role.code)
    return UserSummary(
        id=user.id, employee_code=user.employee_code, full_name=user.full_name, email=user.email,
        department=user.department, is_active=user.is_active, role_code=user.role.code,
    )

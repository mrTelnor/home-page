import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.core.dependencies import AdminUser, DbSession
from app.schemas.auth import AdminUserResponse, PasswordResetConfirm, PasswordResetRequest, ResetLinkResponse
from app.services.auth import get_user_by_id
from app.services.password_reset import (
    confirm_reset,
    create_reset_token,
    get_valid_token,
    list_users_for_admin,
    request_reset,
)

router = APIRouter(prefix="/auth/password-reset", tags=["password-reset"])


@router.post("/request")
async def password_reset_request(data: PasswordResetRequest, session: DbSession):
    return await request_reset(session, data.identifier, data.channel)


@router.post("/confirm")
async def password_reset_confirm(data: PasswordResetConfirm, session: DbSession):
    ok = await confirm_reset(session, data.token, data.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ссылка недействительна или устарела")
    return {"status": "ok"}


@router.get("/validate")
async def password_reset_validate(token: str, session: DbSession):
    return {"valid": await get_valid_token(session, token) is not None}


admin_router = APIRouter(prefix="/auth/admin", tags=["admin"])


@admin_router.get("/users", response_model=list[AdminUserResponse])
async def admin_list_users(session: DbSession, admin: AdminUser):
    return await list_users_for_admin(session)


@admin_router.post("/users/{user_id}/reset-link", response_model=ResetLinkResponse)
async def admin_reset_link(user_id: uuid.UUID, session: DbSession, admin: AdminUser):
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    raw, expires_at = await create_reset_token(session, user, "admin")
    return ResetLinkResponse(link=f"https://{settings.domain}/reset-password?token={raw}", expires_at=expires_at)

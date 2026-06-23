from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import DbSession
from app.schemas.auth import PasswordResetConfirm, PasswordResetRequest
from app.services.password_reset import confirm_reset, get_valid_token, request_reset

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

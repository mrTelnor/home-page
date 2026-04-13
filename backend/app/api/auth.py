from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.security import create_jwt, verify_password
from app.db.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TelegramAuthData,
    TelegramLoginRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.auth import (
    authenticate_user,
    create_user,
    get_user_by_tg_id,
    set_telegram_id,
    update_password,
    update_profile,
)
from app.services.telegram import verify_telegram_auth

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_MAX_AGE = settings.jwt_expire_hours * 3600


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, session: AsyncSession = Depends(get_db)):
    if data.invite_code != settings.invite_code:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid invite code")

    try:
        user = await create_user(session, data.username, data.password)
    except Exception:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    return user


@router.post("/login")
async def login(data: LoginRequest, response: Response, session: AsyncSession = Depends(get_db)):
    user = await authenticate_user(session, data.username, data.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = create_jwt(str(user.id))
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return {"message": "ok"}


@router.post("/logout")
async def logout(response: Response, user: User = Depends(get_current_user)):
    response.delete_cookie(key="access_token")
    return {"message": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UpdateProfileRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fields = data.model_dump(exclude_unset=True)
    user = await update_profile(session, user, fields)
    return user


@router.post("/telegram-verify", response_model=UserResponse)
async def telegram_verify(
    data: TelegramAuthData,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_telegram_auth(data.model_dump(), settings.telegram_bot_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram signature")

    existing = await get_user_by_tg_id(session, data.id)
    if existing and existing.id != user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Telegram already linked to another user")

    user = await set_telegram_id(session, user, data.id)
    return user


@router.post("/telegram-unlink", response_model=UserResponse)
async def telegram_unlink(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user = await set_telegram_id(session, user, None)
    return user


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.password_hash is None or not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid old password")

    await update_password(session, user, data.new_password)
    return {"message": "ok"}


@router.post("/telegram-login", response_model=TokenResponse)
async def telegram_login(
    data: TelegramLoginRequest,
    x_bot_secret: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
):
    if x_bot_secret != settings.bot_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    user = await get_user_by_tg_id(session, data.tg_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found. Link Telegram on the website first.")

    token = create_jwt(str(user.id))
    return TokenResponse(access_token=token)

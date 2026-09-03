import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.dependencies import CurrentUser, DbSession, verify_bot_secret
from app.core.ratelimit import LOGIN_LIMIT, REGISTER_LIMIT, limiter
from app.core.security import constant_time_equals, create_jwt, verify_password
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    NotifiableUserResponse,
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
    email_lock_until,
    get_admin_users,
    get_notifiable_users,
    get_user_by_tg_id,
    set_telegram_id,
    update_password,
    update_profile,
)
from app.services.telegram import mark_telegram_auth_used, verify_telegram_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_MAX_AGE = settings.jwt_expire_hours * 3600
INVALID_CREDENTIALS = "Invalid username or password"


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(REGISTER_LIMIT)
async def register(request: Request, data: RegisterRequest, session: DbSession):
    if not constant_time_equals(data.invite_code, settings.invite_code):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid invite code")

    try:
        user = await create_user(session, data.username, data.password)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken") from exc

    logger.info("User registered: %s", user.username)
    return user


@router.post("/login")
@limiter.limit(LOGIN_LIMIT)
async def login(request: Request, data: LoginRequest, response: Response, session: DbSession):
    user = await authenticate_user(session, data.username, data.password)
    if user is None:
        logger.warning("Failed login attempt for username: %s", data.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)

    token = create_jwt(str(user.id), user.token_version)
    _set_auth_cookie(response, token)
    return {"message": "ok"}


@router.post("/logout")
async def logout(response: Response, user: CurrentUser):
    _ = user
    response.delete_cookie(key="access_token")
    return {"message": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UpdateProfileRequest,
    session: DbSession,
    user: CurrentUser,
):
    fields = data.model_dump(exclude_unset=True)
    if "email" in fields:
        new_email = fields["email"].lower() if fields["email"] else None
        if new_email != user.email:
            until = email_lock_until(user)
            if until is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Сменить email можно только после {until:%d.%m.%Y} (7 дней после смены пароля)",
                )
    try:
        user = await update_profile(session, user, fields)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email уже используется") from exc
    return user


@router.post("/telegram-verify", response_model=UserResponse)
async def telegram_verify(
    data: TelegramAuthData,
    session: DbSession,
    user: CurrentUser,
):
    if not verify_telegram_auth(
        data.model_dump(),
        settings.telegram_bot_token,
        max_age_seconds=settings.telegram_auth_max_age_seconds,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram signature")

    # Replay-защита: одну и ту же подпись нельзя применить дважды в пределах окна
    if not mark_telegram_auth_used(data.hash, settings.telegram_auth_max_age_seconds):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram signature already used")

    existing = await get_user_by_tg_id(session, data.id)
    if existing and existing.id != user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Telegram already linked to another user")

    try:
        user = await set_telegram_id(session, user, data.id)
    except IntegrityError as exc:
        # Гонка: тот же tg_id привязали между проверкой и UPDATE (UNIQUE users.tg_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Telegram already linked to another user"
        ) from exc
    return user


@router.post("/telegram-unlink", response_model=UserResponse)
async def telegram_unlink(session: DbSession, user: CurrentUser):
    user = await set_telegram_id(session, user, None)
    return user


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    response: Response,
    session: DbSession,
    user: CurrentUser,
):
    if user.password_hash is None or not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid old password")

    await update_password(session, user, data.new_password)
    # token_version изменилась — переставляем свежую cookie, чтобы текущее
    # устройство не разлогинилось (остальные токены при этом отозваны)
    _set_auth_cookie(response, create_jwt(str(user.id), user.token_version))
    return {"message": "ok"}


@router.post(
    "/telegram-login",
    response_model=TokenResponse,
    dependencies=[Depends(verify_bot_secret)],
)
async def telegram_login(data: TelegramLoginRequest, session: DbSession):
    user = await get_user_by_tg_id(session, data.tg_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Link Telegram on the website first.",
        )

    token = create_jwt(str(user.id), user.token_version)
    return TokenResponse(access_token=token)


@router.get(
    "/users/notifiable",
    response_model=list[NotifiableUserResponse],
    dependencies=[Depends(verify_bot_secret)],
)
async def notifiable_users(session: DbSession):
    return await get_notifiable_users(session)


@router.get(
    "/users/admins",
    response_model=list[NotifiableUserResponse],
    dependencies=[Depends(verify_bot_secret)],
)
async def admin_users(session: DbSession):
    return await get_admin_users(session)


import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_reset_token, hash_reset_token
from app.db.models.password_reset import PasswordResetToken
from app.db.models.user import User
from app.services.auth import get_user_by_email, get_user_by_id, get_user_by_username, update_password
from app.services.email import send_email
from app.services.telegram import send_telegram_message

logger = logging.getLogger(__name__)

THROTTLE_LIMIT = 5
THROTTLE_WINDOW = timedelta(hours=1)


async def is_throttled(session: AsyncSession, user: User) -> bool:
    since = datetime.now(UTC) - THROTTLE_WINDOW
    result = await session.execute(
        select(func.count())
        .select_from(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.created_at >= since)
    )
    return (result.scalar_one() or 0) >= THROTTLE_LIMIT


async def create_reset_token(session: AsyncSession, user: User, channel: str) -> tuple[str, datetime]:
    # гасим прежние неиспользованные токены пользователя
    await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )
    raw = generate_reset_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.reset_token_ttl_minutes)
    session.add(PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=hash_reset_token(raw),
        channel=channel,
        expires_at=expires_at,
    ))
    await session.commit()
    return raw, expires_at


async def get_valid_token(session: AsyncSession, raw: str) -> PasswordResetToken | None:
    result = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_reset_token(raw),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(UTC),
        )
    )
    return result.scalar_one_or_none()


def _reset_link(raw: str) -> str:
    return f"https://{settings.domain}/reset-password?token={raw}"


def _telegram_text(link: str) -> str:
    return (
        "🔑 Запрос на сброс пароля для аккаунта на telnor.ru.\n"
        f"Ссылка действует {settings.reset_token_ttl_minutes} минут:\n{link}\n"
        "Если это были не вы — проигнорируйте сообщение."
    )


def _email_html(link: str) -> str:
    return (
        "<p>Запрос на сброс пароля для аккаунта на telnor.ru.</p>"
        f'<p>Ссылка действует {settings.reset_token_ttl_minutes} минут: '
        f'<a href="{link}">Сбросить пароль</a></p>'
        "<p>Если это были не вы — проигнорируйте письмо.</p>"
    )


async def _dispatch(session: AsyncSession, user: User, channel: str) -> None:
    if await is_throttled(session, user):
        logger.warning("password reset throttled for user=%s", user.id)
        return
    raw, _ = await create_reset_token(session, user, channel)
    link = _reset_link(raw)
    if channel == "telegram":
        await send_telegram_message(user.tg_id, _telegram_text(link))
    else:
        await send_email(user.email, "Сброс пароля — telnor.ru", _email_html(link))


async def request_reset(session: AsyncSession, identifier: str, channel: str | None) -> dict:
    identifier = identifier.strip()
    if "@" in identifier:
        user = await get_user_by_email(session, identifier)
        if user is not None and user.email:
            await _dispatch(session, user, "email")
        return {"status": "sent"}

    user = await get_user_by_username(session, identifier)
    if user is None:
        return {"status": "no_channels"}
    available = []
    if user.tg_id is not None:
        available.append("telegram")
    if user.email:
        available.append("email")
    if not available:
        return {"status": "no_channels"}
    if channel is not None:
        if channel not in available:
            return {"status": "no_channels"}
        await _dispatch(session, user, channel)
        return {"status": "sent"}
    if len(available) == 1:
        await _dispatch(session, user, available[0])
        return {"status": "sent"}
    return {"status": "choose", "channels": available}


async def confirm_reset(session: AsyncSession, raw: str, new_password: str) -> bool:
    token = await get_valid_token(session, raw)
    if token is None:
        return False
    user = await get_user_by_id(session, token.user_id)
    if user is None:
        return False
    await update_password(session, user, new_password)
    token.used_at = datetime.now(UTC)
    await session.commit()
    return True

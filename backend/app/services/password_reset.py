import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_reset_token, hash_reset_token
from app.db.models.password_reset import PasswordResetToken
from app.db.models.user import User

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

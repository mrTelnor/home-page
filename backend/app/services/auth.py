import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.models.user import User


async def create_user(session: AsyncSession, username: str, password: str) -> User:
    user = User(
        id=uuid.uuid4(),
        username=username.lower(),
        password_hash=hash_password(password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username.lower()))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username.lower()))
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def set_telegram_id(session: AsyncSession, user: User, tg_id: int | None) -> User:
    user.tg_id = tg_id
    await session.commit()
    await session.refresh(user)
    return user


async def update_password(session: AsyncSession, user: User, new_password: str) -> User:
    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalar_one_or_none()


# Поля профиля, которые пользователь может менять через PATCH /auth/me.
# Совпадает с UpdateProfileRequest; защита от setattr произвольных атрибутов.
UPDATABLE_PROFILE_FIELDS = frozenset(
    {"first_name", "birthday", "gender", "is_volkov", "notifications_enabled", "email"}
)

# Эти поля можно явно сбросить в None (передав null), остальные None игнорируются
NULLABLE_PROFILE_FIELDS = frozenset({"first_name", "birthday", "gender", "email"})


async def update_profile(session: AsyncSession, user: User, fields: dict) -> User:
    for key, value in fields.items():
        if key not in UPDATABLE_PROFILE_FIELDS:
            continue
        if key == "email" and value is not None:
            value = value.lower()
        if value is not None or key in NULLABLE_PROFILE_FIELDS:
            setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user


def email_lock_until(user: User) -> datetime | None:
    """Дата, до которой нельзя менять email (или None, если можно)."""
    if user.password_changed_at is None:
        return None
    until = user.password_changed_at + timedelta(days=settings.email_change_lock_days)
    return until if datetime.now(UTC) < until else None


async def get_notifiable_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(User.tg_id.is_not(None), User.notifications_enabled.is_(True))
    )
    return list(result.scalars().all())


async def get_admin_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(User.tg_id.is_not(None), User.role == "admin")
    )
    return list(result.scalars().all())



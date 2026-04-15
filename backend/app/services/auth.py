import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def set_telegram_id(session: AsyncSession, user: User, tg_id: int | None) -> User:
    user.tg_id = tg_id
    await session.commit()
    await session.refresh(user)
    return user


async def update_password(session: AsyncSession, user: User, new_password: str) -> User:
    user.password_hash = hash_password(new_password)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalar_one_or_none()


async def update_profile(session: AsyncSession, user: User, fields: dict) -> User:
    for key, value in fields.items():
        if value is not None or key in ("first_name", "birthday", "gender"):
            setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user


async def get_notifiable_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(User.tg_id.is_not(None), User.notifications_enabled.is_(True))
    )
    return list(result.scalars().all())

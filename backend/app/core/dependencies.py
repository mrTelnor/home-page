import uuid
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import async_session
from app.core.security import decode_jwt
from app.db.models.user import User
from app.services.auth import get_user_by_id

NOT_ALLOWED = "Not allowed"


async def get_db():
    async with async_session() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    session: DbSession,
    access_token: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token = access_token
    if token is None and authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_jwt(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = await get_user_by_id(session, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def verify_cron_or_admin(
    session: DbSession,
    x_cron_secret: Annotated[str | None, Header()] = None,
    access_token: Annotated[str | None, Cookie()] = None,
) -> User | None:
    if x_cron_secret == settings.cron_secret:
        return None

    if access_token is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_ALLOWED)

    payload = decode_jwt(access_token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_ALLOWED)

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_ALLOWED)

    user = await get_user_by_id(session, uuid.UUID(user_id))
    if user is None or user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_ALLOWED)

    return user


CronOrAdmin = Annotated[User | None, Depends(verify_cron_or_admin)]

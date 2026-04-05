from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.security import create_jwt
from app.db.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.services.auth import authenticate_user, create_user

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

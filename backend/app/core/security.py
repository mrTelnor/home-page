import time
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_jwt(user_id: str) -> str:
    expire = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        return None


def create_knowledge_jwt(user_id: str, ttl_seconds: int = 86400) -> str:
    """Подписывает JWT для PostgREST с claim role=knowledge_rw, aud=knowledge.
    Используется только эндпоинтом /api/auth/knowledge-token."""
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "role": "knowledge_rw",
        "aud": "knowledge",
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return pyjwt.encode(payload, settings.knowledge_jwt_secret, algorithm=ALGORITHM)

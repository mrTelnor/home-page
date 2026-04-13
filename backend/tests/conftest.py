"""
Pytest fixtures для тестирования backend.

Используется отдельная тестовая БД `homepage_test` на том же PostgreSQL.
Таблицы создаются один раз за сессию, перед каждым тестом — truncate всех таблиц.
"""

import os

# Задаём переменные окружения ДО импорта приложения (pydantic-settings их читает при инициализации)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://homepage:homepage@localhost:5432/homepage_test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("INVITE_CODE", "test-invite")
os.environ.setdefault("CRON_SECRET", "test-cron-secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("TELEGRAM_BOT_USERNAME", "test_bot")
os.environ.setdefault("BOT_SECRET", "test-bot-secret")

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.dependencies import get_db
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import *  # noqa: F401, F403 — register models
from app.db.models.user import User
from app.main import app

# Engine для setup/teardown (NullPool — каждое соединение свежее, не делится с приложением)
admin_engine = create_async_engine(settings.database_url, poolclass=NullPool)

# Engine для приложения в тестах (через dependency override)
test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
TestSessionMaker = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Создать схемы и таблицы один раз за сессию."""
    async with admin_engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS dinner"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with admin_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP SCHEMA IF EXISTS dinner CASCADE"))
        await conn.execute(text("DROP SCHEMA IF EXISTS auth CASCADE"))
    await admin_engine.dispose()
    await test_engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables():
    """Очистить таблицы перед каждым тестом (используем перед, чтобы избежать гонок после)."""
    async with admin_engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE dinner.votes, dinner.daily_menu_recipes, dinner.daily_menus, "
            "dinner.ingredients, dinner.recipes, auth.sessions, auth.users "
            "RESTART IDENTITY CASCADE"
        ))
    yield


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session для тестов, которым нужен прямой доступ к БД (фикстуры юзеров)."""
    async with TestSessionMaker() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP client с переопределённым get_db — каждый запрос получает новую сессию."""
    async def override_get_db():
        async with TestSessionMaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


async def _create_user(
    session: AsyncSession,
    username: str,
    password: str = "test12345",
    role: str = "user",
    tg_id: int | None = None,
) -> User:
    user = User(
        id=uuid4(),
        username=username,
        password_hash=hash_password(password),
        role=role,
        tg_id=tg_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Обычный пользователь."""
    return await _create_user(db_session, "testuser")


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Пользователь с ролью admin."""
    return await _create_user(db_session, "admin", role="admin")


async def _login(client: AsyncClient, username: str, password: str = "test12345") -> None:
    """Залогинить — cookie сохраняется в клиенте автоматически."""
    response = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, f"Login failed: {response.text}"


@pytest.fixture
async def authed_client(client: AsyncClient, test_user: User) -> AsyncClient:
    """Клиент с cookie залогиненного обычного пользователя."""
    await _login(client, "testuser")
    return client


@pytest.fixture
async def admin_client(client: AsyncClient, admin_user: User) -> AsyncClient:
    """Клиент с cookie залогиненного admin."""
    await _login(client, "admin")
    return client

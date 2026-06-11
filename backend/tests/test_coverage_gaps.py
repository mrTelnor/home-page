"""
Точечные тесты на непокрытые ветки (по coverage report --show-missing).

Стиль — как в остальных tests/: integration через client-фикстуры conftest
либо прямые вызовы сервисов с сессией TestSessionMaker; для health/db/main —
monkeypatch app.api.health.async_session и прямой вызов lifespan/dispose_engine.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import dispose_engine
from app.core.dependencies import get_db
from app.core.security import ALGORITHM, create_jwt, decode_jwt
from app.main import app, lifespan
from app.services.auth import get_user_by_id, update_profile
from app.services.menu import cancel_vote
from app.services.recipe import create_recipe, update_recipe
from app.services.telegram import verify_telegram_auth
from tests.conftest import TestSessionMaker, _create_user_standalone

FAKE_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Прямая сессия к тестовой БД (как в test_services_menu.py)."""
    async with TestSessionMaker() as s:
        yield s


def _token_without_sub() -> str:
    """Валидно подписанный JWT, в payload которого нет sub (dependencies.py:42/89)."""
    expire = datetime.now(UTC) + timedelta(hours=1)
    return jwt.encode({"exp": expire}, settings.jwt_secret, algorithm=ALGORITHM)


# ---------- app/api/health.py: ветка 503 при недоступной БД ----------

class _FailingSessionCtx:
    async def __aenter__(self):
        raise OSError("database is down")

    async def __aexit__(self, *exc_info):
        return False


async def test_health_returns_503_when_db_unavailable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("app.api.health.async_session", lambda: _FailingSessionCtx())

    response = await client.get("/api/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert "database is down" in data["detail"]


# ---------- app/main.py lifespan + app/core/db.py dispose_engine ----------

async def test_lifespan_starts_and_disposes_engine():
    """lifespan логирует старт и на выходе вызывает dispose_engine (main.py:23-25, db.py:10)."""
    async with lifespan(app):
        pass


async def test_dispose_engine_is_idempotent():
    """Повторный dispose безопасен — engine пересоздаёт пул при следующем запросе."""
    await dispose_engine()


# ---------- app/core/dependencies.py ----------

async def test_get_db_yields_real_session():
    """Непереопределённый get_db отдаёт сессию из app.core.db (dependencies.py:17-18)."""
    gen = get_db()
    session = await anext(gen)
    assert isinstance(session, AsyncSession)
    with pytest.raises(StopAsyncIteration):
        await anext(gen)


async def test_me_with_invalid_token_cookie(client: AsyncClient):
    client.cookies.set("access_token", "definitely-not-a-jwt")
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


async def test_me_with_token_without_sub(client: AsyncClient):
    client.cookies.set("access_token", _token_without_sub())
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token payload"


async def test_me_with_token_for_missing_user(client: AsyncClient):
    client.cookies.set("access_token", create_jwt(str(uuid4())))
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "User not found"


async def test_cron_endpoint_wrong_secret_without_cookie(client: AsyncClient):
    """Неверный cron-секрет и нет cookie → 403 (dependencies.py:81)."""
    response = await client.post(
        "/api/menus/create-daily",
        headers={"X-Cron-Secret": "wrong-secret"},
        json={},
    )
    assert response.status_code == 403


async def test_cron_endpoint_with_invalid_token_cookie(client: AsyncClient):
    """Невалидный JWT в cookie → 403 (dependencies.py:85)."""
    client.cookies.set("access_token", "garbage")
    response = await client.post("/api/menus/create-daily", json={})
    assert response.status_code == 403


async def test_cron_endpoint_with_token_without_sub(client: AsyncClient):
    """JWT без sub в cookie → 403 (dependencies.py:89)."""
    client.cookies.set("access_token", _token_without_sub())
    response = await client.post("/api/menus/create-daily", json={})
    assert response.status_code == 403


# ---------- app/core/security.py: decode_jwt с ошибкой ----------

def test_decode_jwt_returns_none_for_invalid_token():
    assert decode_jwt("not-a-jwt") is None


def test_decode_jwt_returns_none_for_wrong_signature():
    token = jwt.encode({"sub": "x"}, "other-secret", algorithm=ALGORITHM)
    assert decode_jwt(token) is None


# ---------- app/services/telegram.py: данные без hash ----------

def test_verify_telegram_auth_without_hash():
    assert verify_telegram_auth({"id": 1, "auth_date": "0"}, "token") is False


# ---------- app/services/recipe.py: update_recipe — все необязательные поля ----------

async def test_update_recipe_description_servings_ingredients(session: AsyncSession):
    author = await _create_user_standalone("recipe_updater")
    recipe = await create_recipe(
        session,
        title="Борщ",
        description="старое",
        servings=4,
        author_id=author.id,
        ingredients=[{"name": "свёкла", "amount": "1", "unit": "шт"}],
    )

    updated = await update_recipe(
        session,
        recipe,
        title=None,
        description="новое описание",
        servings=2,
        ingredients=[
            {"name": "лук", "amount": "2", "unit": "шт"},
            {"name": "соль", "amount": "1"},
        ],
    )

    assert updated.title == "Борщ"  # title=None — не трогаем
    assert updated.description == "новое описание"
    assert updated.servings == 2
    assert sorted(i.name for i in updated.ingredients) == ["лук", "соль"]
    assert next(i for i in updated.ingredients if i.name == "соль").unit is None


# ---------- app/services/auth.py: update_profile игнорирует чужие поля ----------

async def test_update_profile_skips_non_updatable_fields(session: AsyncSession):
    created = await _create_user_standalone("profile_user")
    user = await get_user_by_id(session, created.id)

    updated = await update_profile(
        session, user, {"role": "admin", "username": "hacker", "first_name": "Никита"}
    )

    assert updated.role == "user"
    assert updated.username == "profile_user"
    assert updated.first_name == "Никита"


# ---------- app/services/menu.py: cancel_vote без голоса ----------

async def test_cancel_vote_returns_false_when_no_vote(session: AsyncSession):
    assert await cancel_vote(session, uuid4(), uuid4()) is False


# ---------- app/api/menus.py: идемпотентность finalize/close и ошибки vote ----------

def _sample_recipe(title: str) -> dict:
    return {
        "title": title,
        "description": "desc",
        "servings": 4,
        "ingredients": [{"name": "ing", "amount": "1", "unit": "шт"}],
    }


async def _create_recipes(client: AsyncClient, count: int = 3) -> None:
    for i in range(count):
        await client.post("/api/recipes", json=_sample_recipe(f"Gap Recipe {i}"))


async def test_finalize_already_voting_is_idempotent(admin_client: AsyncClient):
    """Повторный finalize меню в статусе voting возвращает его как есть (menus.py:85)."""
    await _create_recipes(admin_client)
    await admin_client.post("/api/menus/create-daily", json={})
    first = await admin_client.post("/api/menus/finalize", json={})
    assert first.json()["status"] == "voting"

    second = await admin_client.post("/api/menus/finalize", json={})
    assert second.status_code == 200
    assert second.json()["status"] == "voting"


async def test_close_voting_already_closed_is_idempotent(admin_client: AsyncClient):
    """Повторный close-voting закрытого меню возвращает его как есть (menus.py:98)."""
    await _create_recipes(admin_client)
    await admin_client.post("/api/menus/create-daily", json={})
    await admin_client.post("/api/menus/finalize", json={})
    first = await admin_client.post("/api/menus/close-voting", json={})
    assert first.json()["status"] == "closed"

    second = await admin_client.post("/api/menus/close-voting", json={})
    assert second.status_code == 200
    assert second.json()["status"] == "closed"


async def test_vote_menu_not_found(authed_client: AsyncClient):
    response = await authed_client.post(
        f"/api/menus/{FAKE_UUID}/vote", json={"recipe_id": FAKE_UUID}
    )
    assert response.status_code == 404


async def test_cancel_vote_menu_not_found(authed_client: AsyncClient):
    response = await authed_client.delete(f"/api/menus/{FAKE_UUID}/vote")
    assert response.status_code == 404


async def test_cancel_vote_when_not_voting(
    admin_client: AsyncClient, authed_client: AsyncClient
):
    """Отмена голоса в меню со статусом collecting → 400 (menus.py:139)."""
    await _create_recipes(admin_client)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()

    response = await authed_client.delete(f"/api/menus/{menu['id']}/vote")
    assert response.status_code == 400

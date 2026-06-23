from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.db.models.user import User
from tests.conftest import _create_user_standalone, _login, _new_client, _override_get_db
from app.core.dependencies import get_db
from app.main import app


async def test_set_email_in_profile(authed_client: AsyncClient):
    resp = await authed_client.patch("/api/auth/me", json={"email": "Me@Example.com"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


async def test_email_conflict_returns_409(client: AsyncClient):
    await _create_user_standalone("owner", email="taken@example.com")
    app.dependency_overrides[get_db] = _override_get_db
    async with _new_client() as c:
        await _create_user_standalone("grabber")
        await _login(c, "grabber")
        resp = await c.patch("/api/auth/me", json={"email": "taken@example.com"})
        assert resp.status_code == 409
    app.dependency_overrides.clear()


async def test_email_change_blocked_after_password_change(client: AsyncClient):
    recent = datetime.now(UTC) - timedelta(days=1)
    await _create_user_standalone("locked", password_changed_at=recent)
    app.dependency_overrides[get_db] = _override_get_db
    async with _new_client() as c:
        await _login(c, "locked")
        resp = await c.patch("/api/auth/me", json={"email": "new@example.com"})
        assert resp.status_code == 403
    app.dependency_overrides.clear()


async def test_email_change_allowed_after_lock_window(client: AsyncClient):
    old = datetime.now(UTC) - timedelta(days=8)
    await _create_user_standalone("unlocked", password_changed_at=old)
    app.dependency_overrides[get_db] = _override_get_db
    async with _new_client() as c:
        await _login(c, "unlocked")
        resp = await c.patch("/api/auth/me", json={"email": "ok@example.com"})
        assert resp.status_code == 200
    app.dependency_overrides.clear()


async def test_change_password_sets_password_changed_at(authed_client: AsyncClient):
    # сменить пароль, затем смена email должна быть заблокирована
    r1 = await authed_client.post(
        "/api/auth/change-password",
        json={"old_password": "test12345", "new_password": "newpass123"},
    )
    assert r1.status_code == 200
    r2 = await authed_client.patch("/api/auth/me", json={"email": "after@example.com"})
    assert r2.status_code == 403

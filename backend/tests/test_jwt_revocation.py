"""JWT-отзыв через token_version: смена пароля инвалидирует старые токены."""
from httpx import AsyncClient

from app.core.security import create_jwt
from app.db.models.user import User
from tests.conftest import _new_client


async def test_token_wrong_version_rejected(client: AsyncClient, test_user: User):
    """Токен с несовпадающей версией отвергается (эмуляция «старого» токена)."""
    token = create_jwt(str(test_user.id), token_version=999)
    client.cookies.set("access_token", token)
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


async def test_password_change_revokes_old_tokens(authed_client: AsyncClient):
    """После смены пароля старый токен перестаёт работать, а текущее устройство
    остаётся залогиненным (change-password переставляет свежую cookie)."""
    old_cookie = authed_client.cookies.get("access_token")
    assert old_cookie

    r = await authed_client.post(
        "/api/auth/change-password",
        json={"old_password": "test12345", "new_password": "newpass12345"},
    )
    assert r.status_code == 200

    # текущее устройство: cookie обновлена — /me работает
    me_same = await authed_client.get("/api/auth/me")
    assert me_same.status_code == 200

    # старый токен (с другого устройства) больше не валиден
    async with _new_client() as other:
        other.cookies.set("access_token", old_cookie)
        me_old = await other.get("/api/auth/me")
        assert me_old.status_code == 401

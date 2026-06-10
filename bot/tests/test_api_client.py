"""Тесты ApiClient: логин по X-Bot-Secret, кеш токена, retry на 401, служебные ручки."""
import json

import httpx
import pytest
import respx

from app.api_client import ApiClient
from app.config import settings

LOGIN_PATH = "/api/auth/telegram-login"


@pytest.fixture
def mock_api():
    with respx.mock(base_url=settings.backend_url) as router:
        yield router


@pytest.fixture
async def client():
    c = ApiClient()
    yield c
    await c.close()


async def test_get_logs_in_once_and_caches_token(mock_api, client):
    login_route = mock_api.post(LOGIN_PATH).respond(200, json={"access_token": "tok-1"})
    items_route = mock_api.get("/api/menus/today").respond(200, json={"id": "m1"})

    resp1 = await client.get("/api/menus/today", 42)
    resp2 = await client.get("/api/menus/today", 42)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    # Логин выполнен ровно один раз, с X-Bot-Secret и tg_id в теле
    assert login_route.call_count == 1
    login_request = login_route.calls[0].request
    assert login_request.headers["X-Bot-Secret"] == settings.bot_secret
    assert json.loads(login_request.content) == {"tg_id": 42}

    # Оба основных запроса используют закешированный Bearer-токен
    assert items_route.call_count == 2
    for call in items_route.calls:
        assert call.request.headers["Authorization"] == "Bearer tok-1"


async def test_login_404_returns_none(mock_api, client):
    mock_api.post(LOGIN_PATH).respond(404)

    resp = await client.get("/api/menus/today", 99)

    assert resp is None


async def test_401_triggers_relogin_and_retry(mock_api, client):
    tokens = iter(["tok-old", "tok-new"])
    login_route = mock_api.post(LOGIN_PATH).mock(
        side_effect=lambda request: httpx.Response(200, json={"access_token": next(tokens)})
    )
    data_route = mock_api.get("/api/menus/today").mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json={"id": "m1"})]
    )

    resp = await client.get("/api/menus/today", 7)

    assert resp is not None
    assert resp.status_code == 200
    assert login_route.call_count == 2
    assert data_route.call_count == 2
    assert data_route.calls[0].request.headers["Authorization"] == "Bearer tok-old"
    assert data_route.calls[1].request.headers["Authorization"] == "Bearer tok-new"


async def test_relogin_after_401_unlinked_returns_none(mock_api, client):
    """401 на основном запросе + 404 на повторном логине (отвязали) → None."""
    login_responses = iter([
        httpx.Response(200, json={"access_token": "tok-1"}),
        httpx.Response(404),
    ])
    mock_api.post(LOGIN_PATH).mock(side_effect=lambda request: next(login_responses))
    mock_api.get("/api/menus/today").respond(401)

    resp = await client.get("/api/menus/today", 7)

    assert resp is None


@pytest.mark.parametrize("method", ["get", "post", "patch", "delete"])
async def test_http_methods_hit_correct_path_with_auth(mock_api, client, method):
    mock_api.post(LOGIN_PATH).respond(200, json={"access_token": "tok-x"})
    route = mock_api.route(method=method.upper(), path="/api/things/1").respond(200, json={})

    resp = await getattr(client, method)("/api/things/1", 5)

    assert resp is not None
    assert resp.status_code == 200
    assert route.call_count == 1
    assert route.calls[0].request.headers["Authorization"] == "Bearer tok-x"


async def test_get_notifiable_users(mock_api, client):
    users = [{"tg_id": 1, "username": "a"}, {"tg_id": 2, "username": "b"}]
    route = mock_api.get("/api/auth/users/notifiable").respond(200, json=users)

    result = await client.get_notifiable_users()

    assert result == users
    assert route.calls[0].request.headers["X-Bot-Secret"] == settings.bot_secret


async def test_get_admin_users(mock_api, client):
    admins = [{"tg_id": 1, "username": "admin"}]
    route = mock_api.get("/api/auth/users/admins").respond(200, json=admins)

    result = await client.get_admin_users()

    assert result == admins
    assert route.calls[0].request.headers["X-Bot-Secret"] == settings.bot_secret

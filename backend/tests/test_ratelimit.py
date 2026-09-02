"""Rate limiting на публичных auth-эндпоинтах (брутфорс пароля/инвайт-кода).

Лимитер в тестах по умолчанию выключен (conftest: RATE_LIMIT_ENABLED=false),
здесь включаем его точечно и сбрасываем состояние между проверками.
IP берётся из X-Real-Ip (его выставляет Traefik) — разные IP независимы.
"""
import pytest
from httpx import AsyncClient

from app.core.ratelimit import limiter


@pytest.fixture(autouse=True)
def _enable_limiter():
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


async def test_login_rate_limited_per_ip(client: AsyncClient):
    """После порога попыток логина с одного IP — 429."""
    headers = {"X-Real-Ip": "203.0.113.10"}
    body = {"username": "nobody", "password": "wrongpass"}

    seen_429 = False
    for _ in range(30):
        r = await client.post("/api/auth/login", json=body, headers=headers)
        if r.status_code == 429:
            seen_429 = True
            break
        assert r.status_code == 401
    assert seen_429, "лимит логина не сработал"


async def test_login_limit_is_per_ip(client: AsyncClient):
    """Разные IP не делят лимит: второй IP отвечает штатно после блокировки первого."""
    body = {"username": "nobody", "password": "wrongpass"}

    # исчерпываем лимит первого IP
    for _ in range(30):
        r = await client.post("/api/auth/login", json=body, headers={"X-Real-Ip": "203.0.113.11"})
        if r.status_code == 429:
            break

    # другой IP — не заблокирован
    r2 = await client.post("/api/auth/login", json=body, headers={"X-Real-Ip": "203.0.113.12"})
    assert r2.status_code == 401


async def test_register_rate_limited(client: AsyncClient):
    """Брутфорс инвайт-кода через register ограничен."""
    headers = {"X-Real-Ip": "203.0.113.20"}
    body = {"username": "someone", "password": "test12345", "invite_code": "wrong"}

    seen_429 = False
    for _ in range(30):
        r = await client.post("/api/auth/register", json=body, headers=headers)
        if r.status_code == 429:
            seen_429 = True
            break
        assert r.status_code == 403
    assert seen_429, "лимит register не сработал"


async def test_password_reset_request_rate_limited(client: AsyncClient):
    """Спам/энумерация через password-reset/request ограничены по IP."""
    headers = {"X-Real-Ip": "203.0.113.30"}
    body = {"identifier": "ghost", "channel": "telegram"}

    seen_429 = False
    for _ in range(30):
        r = await client.post("/api/auth/password-reset/request", json=body, headers=headers)
        if r.status_code == 429:
            seen_429 = True
            break
    assert seen_429, "лимит password-reset не сработал"

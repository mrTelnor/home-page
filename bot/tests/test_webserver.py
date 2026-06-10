"""Тесты HTTP-endpoints бота (/healthz, /alert) через aiohttp TestClient."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app import webserver
from app.webserver import create_app


@pytest.fixture
async def client():
    bot = MagicMock()
    bot.get_me = AsyncMock()
    bot.send_message = AsyncMock()
    app = create_app(bot)
    async with TestClient(TestServer(app)) as c:
        c.bot = bot
        yield c


async def test_healthz_ok(client):
    resp = await client.get("/healthz")
    assert resp.status == 200
    assert (await resp.json())["status"] == "ok"
    client.bot.get_me.assert_awaited_once()


async def test_healthz_telegram_unreachable(client):
    client.bot.get_me.side_effect = TimeoutError("no route")
    resp = await client.get("/healthz")
    assert resp.status == 503
    assert (await resp.json())["status"] == "error"


async def test_alert_forbidden_without_secret(client):
    resp = await client.post("/alert", json={"text": "boom"})
    assert resp.status == 403
    client.bot.send_message.assert_not_awaited()


async def test_alert_requires_text(client):
    resp = await client.post(
        "/alert", json={}, headers={"X-Cron-Secret": "test-cron-secret"}
    )
    assert resp.status == 400


async def test_alert_sends_to_admins(client, monkeypatch):
    monkeypatch.setattr(
        webserver.api,
        "get_admin_users",
        AsyncMock(return_value=[{"tg_id": 111}, {"tg_id": 222}]),
    )
    resp = await client.post(
        "/alert",
        json={"text": "Бэкап не загрузился"},
        headers={"X-Cron-Secret": "test-cron-secret"},
    )
    assert resp.status == 200
    assert client.bot.send_message.await_count == 2
    sent_text = client.bot.send_message.await_args.kwargs["text"]
    assert "Бэкап не загрузился" in sent_text

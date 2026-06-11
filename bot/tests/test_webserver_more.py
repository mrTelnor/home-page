"""Тесты HTTP-endpoints /notify, /uptime-alert, /check-calendar.

Функции calendar_service мокаются на уровне модуля webserver
(monkeypatch.setattr(webserver, "fetch_events", ...)).
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from aiogram.exceptions import TelegramAPIError
from aiohttp.test_utils import TestClient, TestServer

from app import webserver
from app.calendar_service import TZ, CalendarEvent
from app.webserver import create_app

CRON_HEADERS = {"X-Cron-Secret": "test-cron-secret"}


def make_event(event_id: str = "e1") -> CalendarEvent:
    return CalendarEvent(
        calendar_label="Семья",
        calendar_id="cal1",
        event_id=event_id,
        summary="Врач",
        start=datetime.now(TZ) + timedelta(minutes=60),
        end=None,
        is_all_day=False,
        reminders_minutes=(),
    )


@pytest.fixture
async def client():
    bot = MagicMock()
    bot.get_me = AsyncMock()
    bot.send_message = AsyncMock()
    app = create_app(bot)
    async with TestClient(TestServer(app)) as c:
        c.bot = bot
        yield c


@pytest.fixture
def admins(monkeypatch):
    monkeypatch.setattr(
        webserver.api, "get_admin_users", AsyncMock(return_value=[{"tg_id": 111}])
    )


# --- /notify ---


async def test_notify_forbidden(client):
    resp = await client.post("/notify", json={"event": "menu_created"})
    assert resp.status == 403


async def test_notify_unknown_event(client):
    resp = await client.post("/notify", json={"event": "nope"}, headers=CRON_HEADERS)
    assert resp.status == 400
    assert "unknown event" in (await resp.json())["error"]


async def test_notify_dispatches_handler(client, monkeypatch):
    handler = AsyncMock()
    monkeypatch.setitem(webserver.EVENT_HANDLERS, "menu_created", handler)

    resp = await client.post("/notify", json={"event": "menu_created"}, headers=CRON_HEADERS)

    assert resp.status == 200
    handler.assert_awaited_once_with(client.bot)


# --- /uptime-alert ---


async def test_uptime_alert_forbidden(client):
    resp = await client.post("/uptime-alert?secret=wrong", json={})
    assert resp.status == 403


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("offline", "🔴 <b>backend</b>: DOWN"),
        ("online", "🟢 <b>backend</b>: UP"),
        ("maintenance", "🔧 <b>backend</b>: MAINTENANCE"),
        ("flapping", "⚠️ <b>backend</b>: flapping"),
        ("", "⚠️ <b>backend</b>: unknown"),
    ],
)
async def test_uptime_alert_statuses(client, admins, status, expected):
    resp = await client.post(
        "/uptime-alert?secret=test-uptime-secret",
        json={"monitor_name": "backend", "monitor_status": status},
    )
    assert resp.status == 200
    assert client.bot.send_message.await_args.kwargs["text"] == expected


async def test_uptime_alert_appends_target_and_default_name(client, admins):
    resp = await client.post(
        "/uptime-alert?secret=test-uptime-secret",
        json={"monitor_target": "https://telnor.ru", "monitor_status": "offline"},
    )
    assert resp.status == 200
    text = client.bot.send_message.await_args.kwargs["text"]
    assert "<b>https://telnor.ru</b>: DOWN" in text
    assert "\nhttps://telnor.ru" not in text  # target == name → не дублируется


async def test_uptime_alert_target_differs(client, admins):
    resp = await client.post(
        "/uptime-alert?secret=test-uptime-secret",
        json={
            "monitor_name": "backend",
            "monitor_target": "https://telnor.ru",
            "monitor_status": "online",
        },
    )
    assert resp.status == 200
    assert client.bot.send_message.await_args.kwargs["text"].endswith("\nhttps://telnor.ru")


async def test_uptime_alert_send_error_swallowed(client, admins):
    client.bot.send_message.side_effect = TelegramAPIError(method=MagicMock(), message="blocked")
    resp = await client.post(
        "/uptime-alert?secret=test-uptime-secret",
        json={"monitor_name": "backend", "monitor_status": "offline"},
    )
    assert resp.status == 200


async def test_uptime_alert_unknown_monitor(client, admins):
    resp = await client.post("/uptime-alert?secret=test-uptime-secret", json={})
    assert resp.status == 200
    assert "<b>unknown</b>" in client.bot.send_message.await_args.kwargs["text"]


# --- /check-calendar ---


async def test_check_calendar_forbidden(client):
    resp = await client.post("/check-calendar", json={})
    assert resp.status == 403


async def test_check_calendar_digest_already_sent(client, monkeypatch):
    monkeypatch.setattr(webserver, "mark_digest_sent", MagicMock(return_value=False))
    fetch = MagicMock()
    monkeypatch.setattr(webserver, "fetch_digest_events", fetch)

    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert resp.status == 200
    assert (await resp.json())["skipped"] == "already_sent"
    fetch.assert_not_called()


async def test_check_calendar_digest_ok_with_menu(client, admins, monkeypatch):
    monkeypatch.setattr(webserver, "mark_digest_sent", MagicMock(return_value=True))
    monkeypatch.setattr(
        webserver, "fetch_digest_events", MagicMock(return_value=([make_event()], []))
    )
    menu = {"status": "collecting", "recipes": [{"recipe_id": "r1", "title": "Борщ"}]}
    monkeypatch.setattr(webserver.api, "get_today_menu", AsyncMock(return_value=(menu, None)))

    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert resp.status == 200
    body = await resp.json()
    assert body == {"ok": True, "today": 1, "tomorrow": 0, "menu_included": True, "forced": False}
    text = client.bot.send_message.await_args.kwargs["text"]
    assert "Врач" in text
    assert "Борщ" in text


async def test_check_calendar_digest_force_skips_dedup(client, admins, monkeypatch):
    mark = MagicMock(return_value=False)
    monkeypatch.setattr(webserver, "mark_digest_sent", mark)
    monkeypatch.setattr(webserver, "fetch_digest_events", MagicMock(return_value=([], [])))
    monkeypatch.setattr(webserver.api, "get_today_menu", AsyncMock(return_value=(None, "not_found")))

    resp = await client.post("/check-calendar?digest=true&force=true", headers=CRON_HEADERS)

    assert resp.status == 200
    body = await resp.json()
    assert body["forced"] is True
    assert body["menu_included"] is False
    mark.assert_not_called()


async def test_check_calendar_digest_no_admins(client, monkeypatch):
    monkeypatch.setattr(webserver, "mark_digest_sent", MagicMock(return_value=True))
    monkeypatch.setattr(webserver, "fetch_digest_events", MagicMock(return_value=([], [])))
    monkeypatch.setattr(webserver.api, "get_admin_users", AsyncMock(return_value=[]))

    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert resp.status == 200
    assert (await resp.json())["menu_included"] is False
    client.bot.send_message.assert_not_awaited()


async def test_check_calendar_tick_sends_reminders(client, admins, monkeypatch):
    event = make_event()
    monkeypatch.setattr(webserver, "fetch_events", MagicMock(return_value=[event]))
    monkeypatch.setattr(
        webserver,
        "select_reminders_to_send",
        MagicMock(return_value=([(event, "за 1 час")], {"k": "v"})),
    )
    save = MagicMock()
    monkeypatch.setattr(webserver, "save_sent", save)
    opened = AsyncMock()
    closed = AsyncMock()
    monkeypatch.setattr(webserver, "notify_voting_opened", opened)
    monkeypatch.setattr(webserver, "notify_voting_closed", closed)

    resp = await client.post("/check-calendar", headers=CRON_HEADERS)

    assert resp.status == 200
    assert await resp.json() == {"ok": True, "sent": 1, "events_fetched": 1}
    save.assert_called_once_with({"k": "v"})
    text = client.bot.send_message.await_args.kwargs["text"]
    assert "за 1 час" in text
    assert "Врач" in text
    opened.assert_awaited_once_with(client.bot)
    closed.assert_awaited_once_with(client.bot)


async def test_check_calendar_tick_catchup_error_swallowed(client, admins, monkeypatch):
    monkeypatch.setattr(webserver, "fetch_events", MagicMock(return_value=[]))
    monkeypatch.setattr(webserver, "select_reminders_to_send", MagicMock(return_value=([], {})))
    monkeypatch.setattr(webserver, "save_sent", MagicMock())
    monkeypatch.setattr(
        webserver, "notify_voting_opened", AsyncMock(side_effect=httpx.ConnectError("down"))
    )
    closed = AsyncMock()
    monkeypatch.setattr(webserver, "notify_voting_closed", closed)

    resp = await client.post("/check-calendar", headers=CRON_HEADERS)

    assert resp.status == 200
    assert await resp.json() == {"ok": True, "sent": 0, "events_fetched": 0}
    closed.assert_not_awaited()

"""Тесты HTTP-endpoints /notify, /uptime-alert, /check-calendar.

Функции calendar_service мокаются на уровне модуля webserver
(monkeypatch.setattr(webserver, "fetch_events", ...)).
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError
from aiohttp.test_utils import TestClient, TestServer

from app import webserver
from app.calendar_service import TZ, CalendarEvent, has_event_sent, mark_event_sent
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


def digest_key(tg_id: int) -> str:
    return f"digest:{datetime.now(TZ).date().isoformat()}:{tg_id}"


def network_error() -> TelegramNetworkError:
    return TelegramNetworkError(method=MagicMock(), message="Request timeout error")


@pytest.fixture
async def client(monkeypatch):
    # Досылка дайджеста зависит от времени суток — по умолчанию выключена, чтобы
    # тесты тика не зависели от часа запуска; включается в тестах досылки.
    monkeypatch.setattr(webserver, "_digest_catchup_due", lambda now: False)
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


async def test_uptime_alert_accepts_header_secret(client, admins):
    """Секрет в заголовке X-Uptime-Secret — предпочтительный способ:
    query string оседает в access-логах."""
    resp = await client.post(
        "/uptime-alert",
        json={"monitor_name": "backend", "monitor_status": "offline"},
        headers={"X-Uptime-Secret": "test-uptime-secret"},
    )
    assert resp.status == 200
    assert client.bot.send_message.await_count == 1


async def test_uptime_alert_wrong_header_forbidden(client):
    resp = await client.post(
        "/uptime-alert", json={}, headers={"X-Uptime-Secret": "wrong"}
    )
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


async def test_check_calendar_does_not_block_event_loop(client, admins, monkeypatch):
    """Синхронный Google-вызов должен идти в пуле потоков: пока он «висит»,
    event loop продолжает работать (polling/healthz не морозятся)."""
    import asyncio
    import time

    def slow_fetch(time_min, time_max):
        time.sleep(0.4)  # блокирующий sync-вызов Google API
        return []

    monkeypatch.setattr(webserver, "fetch_events", slow_fetch)
    monkeypatch.setattr(webserver, "select_reminders_to_send", MagicMock(return_value=([], {})))
    monkeypatch.setattr(webserver, "save_sent", MagicMock())
    monkeypatch.setattr(webserver, "notify_voting_opened", AsyncMock())
    monkeypatch.setattr(webserver, "notify_voting_closed", AsyncMock())

    ticks = 0
    stop = False

    async def ticker():
        nonlocal ticks
        while not stop:
            await asyncio.sleep(0.02)
            ticks += 1

    task = asyncio.create_task(ticker())
    resp = await client.post("/check-calendar", headers=CRON_HEADERS)
    ticks_at_return = ticks  # сколько тиков успело пройти ПОКА шёл запрос
    stop = True
    await task

    assert resp.status == 200
    # при блокировке loop тикер во время 0.4с fetch не двигался бы → ticks≈0
    assert ticks_at_return >= 10, f"event loop блокировался: ticks={ticks_at_return}"


@pytest.fixture
def digest_data(monkeypatch):
    """Дайджест с одним событием и без меню."""
    fetch = MagicMock(return_value=([make_event()], []))
    monkeypatch.setattr(webserver, "fetch_digest_events", fetch)
    monkeypatch.setattr(webserver.api, "get_today_menu", AsyncMock(return_value=(None, "not_found")))
    return fetch


async def test_check_calendar_digest_already_sent(client, admins, digest_data):
    mark_event_sent(digest_key(111))

    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert resp.status == 200
    assert (await resp.json())["skipped"] == "already_sent"
    digest_data.assert_not_called()
    client.bot.send_message.assert_not_awaited()


async def test_check_calendar_digest_legacy_marker_counts_as_sent(client, admins, digest_data):
    """Маркер старого формата (без tg_id) — дайджест уже разослан целиком."""
    mark_event_sent(f"digest:{datetime.now(TZ).date().isoformat()}")

    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert (await resp.json())["skipped"] == "already_sent"
    client.bot.send_message.assert_not_awaited()


async def test_check_calendar_digest_ok_with_menu(client, admins, monkeypatch):
    monkeypatch.setattr(
        webserver, "fetch_digest_events", MagicMock(return_value=([make_event()], []))
    )
    menu = {"status": "collecting", "recipes": [{"recipe_id": "r1", "title": "Борщ"}]}
    monkeypatch.setattr(webserver.api, "get_today_menu", AsyncMock(return_value=(menu, None)))

    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert resp.status == 200
    body = await resp.json()
    assert body == {
        "ok": True, "today": 1, "tomorrow": 0, "menu_included": True,
        "forced": False, "sent": 1, "failed": 0,
    }
    kwargs = client.bot.send_message.await_args.kwargs
    assert "Врач" in kwargs["text"]
    assert "Борщ" in kwargs["text"]
    # Короткий таймаут: недоступный Telegram не должен держать запрос cron дольше его -m
    assert kwargs["request_timeout"] == webserver.DIGEST_SEND_TIMEOUT_SEC
    assert has_event_sent(digest_key(111))


async def test_check_calendar_digest_failure_is_503_and_retried(client, admins, digest_data):
    """Регресс (2026-10-03): Telegram был недоступен, а маркер ставился до отправки —
    повтор curl получал already_sent, дайджест терялся без алерта."""
    client.bot.send_message.side_effect = network_error()

    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert resp.status == 503
    body = await resp.json()
    assert body["ok"] is False
    assert (body["sent"], body["failed"]) == (0, 1)
    assert not has_event_sent(digest_key(111))

    client.bot.send_message.side_effect = None
    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert resp.status == 200
    assert (await resp.json())["sent"] == 1


async def test_check_calendar_digest_partial_failure_resends_only_failed(
    client, monkeypatch, digest_data
):
    monkeypatch.setattr(
        webserver.api, "get_admin_users", AsyncMock(return_value=[{"tg_id": 111}, {"tg_id": 222}])
    )

    async def fail_for_222(chat_id, **kwargs):
        if chat_id == 222:
            raise network_error()

    client.bot.send_message.side_effect = fail_for_222

    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert resp.status == 200  # кому-то дошло — остальным дошлёт тик
    body = await resp.json()
    assert (body["sent"], body["failed"]) == (1, 1)

    client.bot.send_message.reset_mock(side_effect=True)
    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert (await resp.json())["sent"] == 1
    assert [c.kwargs["chat_id"] for c in client.bot.send_message.await_args_list] == [222]


async def test_check_calendar_digest_force_skips_dedup(client, admins, digest_data):
    mark_event_sent(digest_key(111))

    resp = await client.post("/check-calendar?digest=true&force=true", headers=CRON_HEADERS)

    assert resp.status == 200
    body = await resp.json()
    assert body["forced"] is True
    assert body["menu_included"] is False
    assert body["sent"] == 1


async def test_check_calendar_digest_no_admins(client, monkeypatch, digest_data):
    monkeypatch.setattr(webserver.api, "get_admin_users", AsyncMock(return_value=[]))

    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert resp.status == 200
    assert (await resp.json())["skipped"] == "no_recipients"
    client.bot.send_message.assert_not_awaited()


# --- досылка дайджеста тиком ---


@pytest.fixture
def quiet_tick(monkeypatch):
    """Тик без напоминаний и voting-досылки."""
    monkeypatch.setattr(webserver, "fetch_events", MagicMock(return_value=[]))
    monkeypatch.setattr(webserver, "select_reminders_to_send", MagicMock(return_value=([], {})))
    monkeypatch.setattr(webserver, "save_sent", MagicMock())
    monkeypatch.setattr(webserver, "notify_voting_opened", AsyncMock())
    monkeypatch.setattr(webserver, "notify_voting_closed", AsyncMock())


@pytest.mark.parametrize(
    ("hhmm", "due"),
    [("08:00", False), ("08:05", True), ("11:55", True), ("12:00", False), ("23:00", False)],
)
def test_digest_catchup_window(hhmm, due):
    hour, minute = map(int, hhmm.split(":"))
    now = datetime(2026, 10, 3, hour, minute, tzinfo=TZ)
    assert webserver._digest_catchup_due(now) is due


async def test_tick_catches_up_undelivered_digest(client, admins, digest_data, quiet_tick, monkeypatch):
    monkeypatch.setattr(webserver, "_digest_catchup_due", lambda now: True)

    resp = await client.post("/check-calendar", headers=CRON_HEADERS)

    assert resp.status == 200
    assert "Расписание на сегодня" in client.bot.send_message.await_args.kwargs["text"]
    assert has_event_sent(digest_key(111))

    client.bot.send_message.reset_mock()
    await client.post("/check-calendar", headers=CRON_HEADERS)
    client.bot.send_message.assert_not_awaited()  # следующий тик не дублирует


async def test_tick_outside_window_does_not_send_digest(client, admins, digest_data, quiet_tick):
    resp = await client.post("/check-calendar", headers=CRON_HEADERS)

    assert resp.status == 200
    client.bot.send_message.assert_not_awaited()


async def test_tick_digest_catchup_error_swallowed(client, quiet_tick, monkeypatch):
    monkeypatch.setattr(webserver, "_digest_catchup_due", lambda now: True)
    monkeypatch.setattr(
        webserver.api, "get_admin_users", AsyncMock(side_effect=httpx.ConnectError("down"))
    )

    resp = await client.post("/check-calendar", headers=CRON_HEADERS)

    assert resp.status == 200


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

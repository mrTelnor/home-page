"""Раздельные уведомления: ужины (notifications_enabled) и календарь
(calendar_notifications_enabled) — хендлер /notifications и фильтры рассылок."""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app import api_client, notify, webserver
from app.api_client import NOT_LINKED_MSG
from app.calendar_service import TZ, CalendarEvent
from app.handlers import notifications
from app.helpers import SERVICE_UNAVAILABLE_MSG
from app.webserver import create_app

CRON_HEADERS = {"X-Cron-Secret": "test-cron-secret"}

ADMIN = {"role": "admin", "notifications_enabled": True, "calendar_notifications_enabled": True}
USER = {"role": "user", "notifications_enabled": True, "calendar_notifications_enabled": True}


def make_response(status_code: int = 200, json_data=None) -> Mock:
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def make_message(tg_id: int = 1) -> MagicMock:
    msg = MagicMock()
    msg.from_user.id = tg_id
    msg.answer = AsyncMock()
    return msg


def make_callback(data: str, tg_id: int = 1) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = tg_id
    cb.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    return cb


def button_texts(markup) -> list[str]:
    return [row[0].text for row in markup.inline_keyboard]


# --- /notifications ---


async def test_cmd_notifications_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=None))
    msg = make_message()

    await notifications.cmd_notifications(msg)

    msg.answer.assert_awaited_once_with(NOT_LINKED_MSG)


async def test_cmd_notifications_admin_sees_both_toggles(monkeypatch):
    user = {**ADMIN, "calendar_notifications_enabled": False}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, user)))
    msg = make_message()

    await notifications.cmd_notifications(msg)

    markup = msg.answer.await_args.kwargs["reply_markup"]
    assert button_texts(markup) == ["🍽 Ужины: ✅ вкл", "📅 Календарь: 🔇 выкл"]
    assert [row[0].callback_data for row in markup.inline_keyboard] == ["notif:dinner", "notif:calendar"]


async def test_cmd_notifications_user_sees_only_dinner(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, USER)))
    msg = make_message()

    await notifications.cmd_notifications(msg)

    markup = msg.answer.await_args.kwargs["reply_markup"]
    assert button_texts(markup) == ["🍽 Ужины: ✅ вкл"]


async def test_toggle_calendar_admin(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, ADMIN)))
    updated = {**ADMIN, "calendar_notifications_enabled": False}
    patch_mock = AsyncMock(return_value=make_response(200, updated))
    monkeypatch.setattr(api_client.api, "patch", patch_mock)
    cb = make_callback("notif:calendar")

    await notifications.cb_toggle_notifications(cb)

    patch_mock.assert_awaited_once_with("/api/auth/me", 1, json={"calendar_notifications_enabled": False})
    markup = cb.message.edit_text.await_args.kwargs["reply_markup"]
    assert button_texts(markup) == ["🍽 Ужины: ✅ вкл", "📅 Календарь: 🔇 выкл"]
    cb.answer.assert_awaited_once_with("Выключено.")


async def test_toggle_dinner_back_on(monkeypatch):
    user = {**USER, "notifications_enabled": False}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, user)))
    patch_mock = AsyncMock(return_value=make_response(200, USER))
    monkeypatch.setattr(api_client.api, "patch", patch_mock)
    cb = make_callback("notif:dinner")

    await notifications.cb_toggle_notifications(cb)

    patch_mock.assert_awaited_once_with("/api/auth/me", 1, json={"notifications_enabled": True})
    cb.answer.assert_awaited_once_with("Включено.")


async def test_toggle_calendar_rejected_for_non_admin(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, USER)))
    patch_mock = AsyncMock()
    monkeypatch.setattr(api_client.api, "patch", patch_mock)
    cb = make_callback("notif:calendar")

    await notifications.cb_toggle_notifications(cb)

    patch_mock.assert_not_awaited()
    cb.answer.assert_awaited_once_with("Календарь доступен только администраторам.")


async def test_toggle_unknown_kind(monkeypatch):
    get_mock = AsyncMock()
    monkeypatch.setattr(api_client.api, "get", get_mock)
    cb = make_callback("notif:weather")

    await notifications.cb_toggle_notifications(cb)

    get_mock.assert_not_awaited()
    cb.answer.assert_awaited_once_with("Неизвестная настройка.")


async def test_toggle_backend_error(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, ADMIN)))
    monkeypatch.setattr(api_client.api, "patch", AsyncMock(return_value=make_response(500)))
    cb = make_callback("notif:dinner")

    await notifications.cb_toggle_notifications(cb)

    cb.message.edit_text.assert_not_awaited()
    cb.answer.assert_awaited_once_with(SERVICE_UNAVAILABLE_MSG)


# --- broadcast: кого исключать из menu_created ---


async def test_menu_created_goes_to_admin_without_calendar(monkeypatch):
    """Админ, выключивший календарь, не получит дайджест — меню ему шлём обычным сообщением."""
    monkeypatch.setattr(
        api_client.api,
        "get_notifiable_users",
        AsyncMock(return_value=[{"tg_id": 1}, {"tg_id": 2}, {"tg_id": 3}]),
    )
    monkeypatch.setattr(
        api_client.api,
        "get_admin_users",
        AsyncMock(return_value=[
            {"tg_id": 1, "calendar_notifications_enabled": True},
            {"tg_id": 2, "calendar_notifications_enabled": False},
        ]),
    )
    bot = MagicMock()
    bot.send_message = AsyncMock()

    await notify.broadcast(bot, "меню", exclude_digest_recipients=True)

    assert [c.kwargs["chat_id"] for c in bot.send_message.await_args_list] == [2, 3]


# --- /check-calendar: фильтр получателей ---


def make_event() -> CalendarEvent:
    return CalendarEvent(
        calendar_label="Семья",
        calendar_id="cal1",
        event_id="e1",
        summary="Врач",
        start=datetime.now(TZ) + timedelta(minutes=60),
        end=None,
        is_all_day=False,
        reminders_minutes=(),
    )


ADMINS = [
    {"tg_id": 111, "notifications_enabled": True, "calendar_notifications_enabled": True},
    {"tg_id": 222, "notifications_enabled": False, "calendar_notifications_enabled": True},
    {"tg_id": 333, "notifications_enabled": True, "calendar_notifications_enabled": False},
]


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(webserver.api, "get_admin_users", AsyncMock(return_value=ADMINS))
    bot = MagicMock()
    bot.send_message = AsyncMock()
    async with TestClient(TestServer(create_app(bot))) as c:
        c.bot = bot
        yield c


def sent(client) -> dict[int, str]:
    return {c.kwargs["chat_id"]: c.kwargs["text"] for c in client.bot.send_message.await_args_list}


async def test_reminders_skip_admins_without_calendar(client, monkeypatch):
    event = make_event()
    monkeypatch.setattr(webserver, "fetch_events", MagicMock(return_value=[event]))
    monkeypatch.setattr(
        webserver, "select_reminders_to_send", MagicMock(return_value=([(event, "за 1 час")], {}))
    )
    monkeypatch.setattr(webserver, "save_sent", MagicMock())
    monkeypatch.setattr(webserver, "notify_voting_opened", AsyncMock())
    monkeypatch.setattr(webserver, "notify_voting_closed", AsyncMock())

    resp = await client.post("/check-calendar", headers=CRON_HEADERS)

    assert resp.status == 200
    assert set(sent(client)) == {111, 222}


async def test_digest_menu_only_for_dinner_subscribers(client, monkeypatch):
    monkeypatch.setattr(webserver, "mark_digest_sent", MagicMock(return_value=True))
    monkeypatch.setattr(webserver, "fetch_digest_events", MagicMock(return_value=([make_event()], [])))
    menu = {"status": "collecting", "recipes": [{"recipe_id": "r1", "title": "Борщ"}]}
    monkeypatch.setattr(webserver.api, "get_today_menu", AsyncMock(return_value=(menu, None)))

    resp = await client.post("/check-calendar?digest=true", headers=CRON_HEADERS)

    assert resp.status == 200
    texts = sent(client)
    assert set(texts) == {111, 222}  # 333 выключил календарь
    assert "Врач" in texts[111] and "Борщ" in texts[111]
    assert "Врач" in texts[222] and "Борщ" not in texts[222]


async def test_alerts_ignore_notification_toggles(client):
    resp = await client.post("/alert", json={"text": "Бэкап упал"}, headers=CRON_HEADERS)

    assert resp.status == 200
    assert set(sent(client)) == {111, 222, 333}

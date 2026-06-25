"""Тесты app.notify: broadcast и событийные уведомления.

API мокается на singleton api_client.api, дедуп mark_event_sent — на модуле notify.
"""
from unittest.mock import AsyncMock, MagicMock, call

from aiogram.exceptions import TelegramAPIError

from app import api_client, notify

MENU_VOTING = {
    "id": "m1",
    "status": "voting",
    "recipes": [
        {"recipe_id": "r1", "title": "Борщ", "votes_count": 2},
        {"recipe_id": "r2", "title": "Плов", "votes_count": 1},
    ],
    "winner_recipe_id": None,
}


def make_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


def tg_error() -> TelegramAPIError:
    return TelegramAPIError(method=MagicMock(), message="blocked")


# --- broadcast ---


async def test_broadcast_sends_to_all(monkeypatch):
    monkeypatch.setattr(
        api_client.api,
        "get_notifiable_users",
        AsyncMock(return_value=[{"tg_id": 1}, {"tg_id": 2}]),
    )
    bot = make_bot()

    await notify.broadcast(bot, "привет")

    assert bot.send_message.await_args_list == [
        call(chat_id=1, text="привет"),
        call(chat_id=2, text="привет"),
    ]


async def test_broadcast_survives_telegram_error(monkeypatch):
    monkeypatch.setattr(
        api_client.api,
        "get_notifiable_users",
        AsyncMock(return_value=[{"tg_id": 1}, {"tg_id": 2}]),
    )
    bot = make_bot()
    bot.send_message.side_effect = [tg_error(), None]

    await notify.broadcast(bot, "привет")

    assert bot.send_message.await_count == 2


async def test_broadcast_exclude_admins(monkeypatch):
    monkeypatch.setattr(
        api_client.api,
        "get_notifiable_users",
        AsyncMock(return_value=[{"tg_id": 1}, {"tg_id": 2}]),
    )
    monkeypatch.setattr(
        api_client.api, "get_admin_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    bot = make_bot()

    await notify.broadcast(bot, "текст", exclude_admins=True)

    bot.send_message.assert_awaited_once_with(chat_id=2, text="текст")


# --- notify_menu_created ---


async def test_notify_menu_created_no_users(monkeypatch):
    monkeypatch.setattr(api_client.api, "get_notifiable_users", AsyncMock(return_value=[]))
    get_menu = AsyncMock()
    monkeypatch.setattr(api_client.api, "get_today_menu", get_menu)

    await notify.notify_menu_created(make_bot())

    get_menu.assert_not_awaited()


async def test_notify_menu_created_no_menu(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(None, "not_found")))
    bot = make_bot()

    await notify.notify_menu_created(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_menu_created_broadcasts_excluding_admins(monkeypatch):
    monkeypatch.setattr(
        api_client.api,
        "get_notifiable_users",
        AsyncMock(return_value=[{"tg_id": 1}, {"tg_id": 2}]),
    )
    monkeypatch.setattr(
        api_client.api, "get_admin_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(MENU_VOTING, None)))
    bot = make_bot()

    await notify.notify_menu_created(bot)

    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.kwargs["chat_id"] == 2
    text = bot.send_message.await_args.kwargs["text"]
    assert "Меню дня готово" in text
    assert "Борщ" in text


# --- notify_voting_opened ---


async def test_notify_voting_opened_no_users(monkeypatch):
    monkeypatch.setattr(api_client.api, "get_notifiable_users", AsyncMock(return_value=[]))
    bot = make_bot()

    await notify.notify_voting_opened(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_voting_opened_no_menu(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(None, "not_found")))
    bot = make_bot()

    await notify.notify_voting_opened(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_voting_opened_wrong_status(monkeypatch):
    menu = {**MENU_VOTING, "status": "collecting"}
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(menu, None)))
    bot = make_bot()

    await notify.notify_voting_opened(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_voting_opened_already_sent(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(MENU_VOTING, None)))
    monkeypatch.setattr(notify, "mark_event_sent", MagicMock(return_value=False))
    bot = make_bot()

    await notify.notify_voting_opened(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_voting_opened_ok(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(MENU_VOTING, None)))
    mark = MagicMock(return_value=True)
    monkeypatch.setattr(notify, "mark_event_sent", mark)
    bot = make_bot()

    await notify.notify_voting_opened(bot)

    mark.assert_called_once_with("voting_opened:m1")
    bot.send_message.assert_awaited_once()
    text = bot.send_message.await_args.kwargs["text"]
    assert "Голосование за ужин открыто" in text
    assert "Борщ" in text
    assert "/vote" in text


# --- notify_voting_closed ---


async def test_notify_voting_closed_no_users(monkeypatch):
    monkeypatch.setattr(api_client.api, "get_notifiable_users", AsyncMock(return_value=[]))
    bot = make_bot()

    await notify.notify_voting_closed(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_voting_closed_no_menu(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(None, "not_found")))
    bot = make_bot()

    await notify.notify_voting_closed(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_voting_closed_wrong_status(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(MENU_VOTING, None)))
    bot = make_bot()

    await notify.notify_voting_closed(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_voting_closed_already_sent(monkeypatch):
    menu = {**MENU_VOTING, "status": "closed", "winner_recipe_id": "r1"}
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(menu, None)))
    monkeypatch.setattr(notify, "mark_event_sent", MagicMock(return_value=False))
    bot = make_bot()

    await notify.notify_voting_closed(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_voting_closed_ok(monkeypatch):
    menu = {**MENU_VOTING, "status": "closed", "winner_recipe_id": "r1"}
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(menu, None)))
    mark = MagicMock(return_value=True)
    monkeypatch.setattr(notify, "mark_event_sent", mark)
    bot = make_bot()

    await notify.notify_voting_closed(bot)

    mark.assert_called_once_with("voting_closed:m1")
    kwargs = bot.send_message.await_args.kwargs
    text = kwargs["text"]
    assert kwargs["parse_mode"] == "HTML"
    assert 'Победитель: <a href="https://telnor.ru/recipes/r1">Борщ</a>' in text
    assert "Борщ — 2 гол. 🏆" in text
    assert "Плов — 1 гол." in text


async def test_notify_voting_closed_no_winner(monkeypatch):
    menu = {**MENU_VOTING, "status": "closed", "winner_recipe_id": None}
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(menu, None)))
    monkeypatch.setattr(notify, "mark_event_sent", MagicMock(return_value=True))
    bot = make_bot()

    await notify.notify_voting_closed(bot)

    assert "Победитель: Не определён" in bot.send_message.await_args.kwargs["text"]


# --- notify_recipe_suggested ---


async def test_notify_recipe_suggested_excludes_author(monkeypatch):
    monkeypatch.setattr(
        api_client.api,
        "get_notifiable_users",
        AsyncMock(return_value=[{"tg_id": 1}, {"tg_id": 2}, {"tg_id": 3}]),
    )
    bot = make_bot()
    bot.send_message.side_effect = [tg_error(), None]

    await notify.notify_recipe_suggested(bot, "Никита", "Борщ", exclude_tg_id=2)

    assert [c.kwargs["chat_id"] for c in bot.send_message.await_args_list] == [1, 3]
    assert "Никита предложил к голосованию: Борщ" in bot.send_message.await_args.kwargs["text"]


# --- EVENT_HANDLERS ---


def test_event_handlers_mapping():
    assert notify.EVENT_HANDLERS == {
        "menu_created": notify.notify_menu_created,
        "voting_opened": notify.notify_voting_opened,
        "voting_closed": notify.notify_voting_closed,
    }

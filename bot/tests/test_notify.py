"""Тесты app.notify: broadcast и событийные уведомления.

API мокается на singleton api_client.api, дедуп mark_event_sent — на модуле notify.
"""
from unittest.mock import AsyncMock, MagicMock, call

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter

from app import api_client, notify


def make_dedup_store(monkeypatch) -> set:
    """Фейковый дедуп-стор вместо JSON-файла: set ключей."""
    store: set[str] = set()
    monkeypatch.setattr(notify, "has_event_sent", lambda k: k in store, raising=False)

    def mark(key: str) -> bool:
        if key in store:
            return False
        store.add(key)
        return True

    monkeypatch.setattr(notify, "mark_event_sent", mark)
    return store

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


async def test_notify_voting_opened_already_sent_legacy_key(monkeypatch):
    """Событийный ключ старого формата (без tg_id) блокирует рассылку целиком."""
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(MENU_VOTING, None)))
    store = make_dedup_store(monkeypatch)
    store.add("voting_opened:m1")
    bot = make_bot()

    await notify.notify_voting_opened(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_voting_opened_ok(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(MENU_VOTING, None)))
    store = make_dedup_store(monkeypatch)
    bot = make_bot()

    await notify.notify_voting_opened(bot)

    assert "voting_opened:m1:1" in store
    bot.send_message.assert_awaited_once()
    text = bot.send_message.await_args.kwargs["text"]
    assert "Голосование за ужин открыто" in text
    assert "Борщ" in text
    assert "/vote" in text


async def test_notify_voting_opened_resends_only_to_failed(monkeypatch):
    """Провал отправки одному пользователю не помечает событие отправленным:
    повторный вызов (catch-up) дошлёт только ему, а третий — никому."""
    monkeypatch.setattr(
        api_client.api,
        "get_notifiable_users",
        AsyncMock(return_value=[{"tg_id": 1}, {"tg_id": 2}]),
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(MENU_VOTING, None)))
    make_dedup_store(monkeypatch)

    bot = make_bot()
    bot.send_message.side_effect = [tg_error(), None]  # 1 — провал, 2 — доставлено
    await notify.notify_voting_opened(bot)

    bot2 = make_bot()
    await notify.notify_voting_opened(bot2)
    assert [c.kwargs["chat_id"] for c in bot2.send_message.await_args_list] == [1]

    bot3 = make_bot()
    await notify.notify_voting_opened(bot3)
    bot3.send_message.assert_not_awaited()


async def test_notify_voting_opened_forbidden_not_retried(monkeypatch):
    """Заблокировавший бота пользователь помечается обработанным —
    catch-up не долбит его каждые 5 минут."""
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(MENU_VOTING, None)))
    store = make_dedup_store(monkeypatch)
    bot = make_bot()
    bot.send_message.side_effect = TelegramForbiddenError(method=MagicMock(), message="bot was blocked")

    await notify.notify_voting_opened(bot)

    assert "voting_opened:m1:1" in store


async def test_broadcast_retries_after_flood_control(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    bot = make_bot()
    bot.send_message.side_effect = [
        TelegramRetryAfter(method=MagicMock(), message="flood", retry_after=0),
        None,
    ]

    await notify.broadcast(bot, "привет")

    assert bot.send_message.await_count == 2


async def test_notify_menu_created_escapes_html(monkeypatch):
    menu = {**MENU_VOTING, "recipes": [{"recipe_id": "r1", "title": "Курица <гриль> & Ко", "votes_count": 0}]}
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_admin_users", AsyncMock(return_value=[]))
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(menu, None)))
    bot = make_bot()

    await notify.notify_menu_created(bot)

    text = bot.send_message.await_args.kwargs["text"]
    assert "&lt;гриль&gt; &amp; Ко" in text
    assert "<гриль>" not in text


async def test_notify_voting_opened_escapes_html(monkeypatch):
    menu = {**MENU_VOTING, "recipes": [{"recipe_id": "r1", "title": "Суп <острый>", "votes_count": 0}]}
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(menu, None)))
    make_dedup_store(monkeypatch)
    bot = make_bot()

    await notify.notify_voting_opened(bot)

    text = bot.send_message.await_args.kwargs["text"]
    assert "Суп &lt;острый&gt;" in text
    assert "<острый>" not in text


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


async def test_notify_voting_closed_already_sent_legacy_key(monkeypatch):
    menu = {**MENU_VOTING, "status": "closed", "winner_recipe_id": "r1"}
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(menu, None)))
    store = make_dedup_store(monkeypatch)
    store.add("voting_closed:m1")
    bot = make_bot()

    await notify.notify_voting_closed(bot)

    bot.send_message.assert_not_awaited()


async def test_notify_voting_closed_ok(monkeypatch):
    menu = {**MENU_VOTING, "status": "closed", "winner_recipe_id": "r1"}
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(menu, None)))
    store = make_dedup_store(monkeypatch)
    bot = make_bot()

    await notify.notify_voting_closed(bot)

    assert "voting_closed:m1:1" in store
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
    make_dedup_store(monkeypatch)
    bot = make_bot()

    await notify.notify_voting_closed(bot)

    assert "Победитель: Не определён" in bot.send_message.await_args.kwargs["text"]


async def test_notify_voting_closed_escapes_winner_in_link(monkeypatch):
    menu = {
        **MENU_VOTING,
        "status": "closed",
        "winner_recipe_id": "r1",
        "recipes": [{"recipe_id": "r1", "title": "Q&A <фирменный>", "votes_count": 3}],
    }
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    monkeypatch.setattr(api_client.api, "get_today_menu", AsyncMock(return_value=(menu, None)))
    make_dedup_store(monkeypatch)
    bot = make_bot()

    await notify.notify_voting_closed(bot)

    text = bot.send_message.await_args.kwargs["text"]
    assert ">Q&amp;A &lt;фирменный&gt;</a>" in text
    assert "<фирменный>" not in text


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


async def test_notify_recipe_suggested_escapes_html(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get_notifiable_users", AsyncMock(return_value=[{"tg_id": 1}])
    )
    bot = make_bot()

    await notify.notify_recipe_suggested(bot, "Ник <б>", "Соус \"чили\" & мёд", exclude_tg_id=99)

    text = bot.send_message.await_args.kwargs["text"]
    assert "Ник &lt;б&gt;" in text
    assert "&amp; мёд" in text
    assert "<б>" not in text


# --- EVENT_HANDLERS ---


def test_event_handlers_mapping():
    assert notify.EVENT_HANDLERS == {
        "menu_created": notify.notify_menu_created,
        "voting_opened": notify.notify_voting_opened,
        "voting_closed": notify.notify_voting_closed,
    }

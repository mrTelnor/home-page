"""Хендлеры не должны падать, когда backend отвечает не-200 (5xx/4xx):
раньше resp.json() вызывался без проверки статуса → KeyError/исключение,
и бот молча «замолкал»."""
from unittest.mock import AsyncMock, MagicMock, Mock

from app import api_client
from app.callbacks import RECIPES_PAGE_PREFIX, pack
from app.handlers.recipes import cb_recipes_page, cmd_recipes
from app.handlers.start import cmd_start
from app.handlers.vote import cb_cancel_vote


def make_response(status_code: int = 200, json_data=None) -> Mock:
    resp = Mock()
    resp.status_code = status_code
    # при не-200 тело может быть чем угодно (или бросать) — проверять статус ДО json()
    resp.json.return_value = json_data if json_data is not None else {"detail": "boom"}
    return resp


def make_message(tg_id: int = 1) -> MagicMock:
    msg = MagicMock()
    msg.from_user.id = tg_id
    msg.answer = AsyncMock()
    return msg


def make_callback(tg_id: int = 1) -> MagicMock:
    cb = MagicMock()
    cb.from_user.id = tg_id
    cb.data = "x"
    cb.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    return cb


async def test_cmd_start_backend_error_does_not_crash(monkeypatch):
    # /me вернул 500 — не должно быть KeyError на user["username"]
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(500)))
    msg = make_message()

    await cmd_start(msg)  # не бросает

    msg.answer.assert_awaited_once()
    assert "username" not in msg.answer.await_args.args[0].lower()


async def test_cmd_recipes_backend_error_shows_message(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(503)))
    msg = make_message()

    await cmd_recipes(msg)

    msg.answer.assert_awaited_once()  # общая ошибка, без падения


async def test_cb_recipes_page_backend_error_does_not_crash(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(500)))
    cb = make_callback()
    cb.data = pack(RECIPES_PAGE_PREFIX, 1)

    await cb_recipes_page(cb)  # не бросает

    cb.answer.assert_awaited()
    cb.message.edit_reply_markup.assert_not_awaited()


async def test_cb_cancel_vote_backend_error_does_not_crash(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get_today_menu", AsyncMock(return_value=({"id": "m1"}, None))
    )
    monkeypatch.setattr(api_client.api, "delete", AsyncMock(return_value=make_response(400)))
    cb = make_callback()

    await cb_cancel_vote(cb)  # не бросает на menu["recipes"]

    cb.answer.assert_awaited()
    cb.message.edit_text.assert_not_awaited()

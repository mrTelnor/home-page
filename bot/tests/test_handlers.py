"""Smoke-тесты хендлеров /menu, /vote (callback), /suggest.

Хендлеры используют singleton `api` из app.api_client, поэтому мокаем методы
прямо на объекте (monkeypatch.setattr(api, ...)) — это видно во всех модулях.
"""
from unittest.mock import AsyncMock, MagicMock, Mock

from app import api_client
from app.api_client import NOT_LINKED_MSG
from app.handlers.menu import cmd_menu
from app.handlers.suggest import SuggestStates, cmd_suggest
from app.handlers.vote import cb_vote, cmd_vote

MENU_VOTING = {
    "id": "m1",
    "status": "voting",
    "recipes": [
        {"recipe_id": "r1", "title": "Борщ", "votes_count": 0},
        {"recipe_id": "r2", "title": "Плов", "votes_count": 1},
    ],
    "user_voted_recipe_id": None,
    "winner_recipe_id": None,
}


def make_response(status_code: int = 200, json_data=None) -> Mock:
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


def make_message(tg_id: int = 1, text: str | None = None) -> MagicMock:
    msg = MagicMock()
    msg.from_user.id = tg_id
    msg.text = text
    msg.answer = AsyncMock()
    return msg


def make_callback(data: str, tg_id: int = 1) -> MagicMock:
    cb = MagicMock()
    cb.data = data
    cb.from_user.id = tg_id
    cb.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.delete = AsyncMock()
    return cb


# --- /menu ---


async def test_cmd_menu_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=None))
    msg = make_message()

    await cmd_menu(msg)

    msg.answer.assert_awaited_once_with(NOT_LINKED_MSG)


async def test_cmd_menu_no_menu_yet(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(404)))
    msg = make_message()

    await cmd_menu(msg)

    msg.answer.assert_awaited_once_with("Меню ещё не создано.")


async def test_cmd_menu_happy_path(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    msg = make_message()

    await cmd_menu(msg)

    msg.answer.assert_awaited_once()
    text = msg.answer.await_args.args[0]
    assert "Борщ" in text
    assert "Плов" in text
    assert "Голосование" in text


# --- /vote ---


async def test_cmd_vote_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=None))
    msg = make_message()

    await cmd_vote(msg)

    msg.answer.assert_awaited_once_with(NOT_LINKED_MSG)


async def test_cmd_vote_open_shows_keyboard(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    msg = make_message()

    await cmd_vote(msg)

    msg.answer.assert_awaited_once()
    assert "Голосование открыто" in msg.answer.await_args.args[0]
    keyboard = msg.answer.await_args.kwargs["reply_markup"]
    callback_data = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert callback_data == ["v:r1", "v:r2"]


async def test_cb_vote_success(monkeypatch):
    voted_menu = {**MENU_VOTING, "user_voted_recipe_id": "r1"}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    post_mock = AsyncMock(return_value=make_response(200, voted_menu))
    monkeypatch.setattr(api_client.api, "post", post_mock)
    cb = make_callback(data="v:r1")

    await cb_vote(cb)

    post_mock.assert_awaited_once_with("/api/menus/m1/vote", 1, json={"recipe_id": "r1"})
    cb.message.edit_text.assert_awaited_once()
    assert "Борщ" in cb.message.edit_text.await_args.args[0]
    cb.answer.assert_awaited_once_with("Голос принят!")


async def test_cb_vote_already_voted(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    monkeypatch.setattr(api_client.api, "post", AsyncMock(return_value=make_response(409)))
    cb = make_callback(data="v:r2")

    await cb_vote(cb)

    cb.answer.assert_awaited_once_with("Вы уже голосовали. Сначала отмените голос.")
    cb.message.edit_text.assert_not_awaited()


# --- /suggest ---


async def test_cmd_suggest_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=None))
    msg = make_message()
    state = AsyncMock()

    await cmd_suggest(msg, state)

    msg.answer.assert_awaited_once_with(NOT_LINKED_MSG)
    state.set_state.assert_not_awaited()


async def test_cmd_suggest_collecting_sets_state(monkeypatch):
    menu = {**MENU_VOTING, "status": "collecting"}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, menu)))
    msg = make_message()
    state = AsyncMock()

    await cmd_suggest(msg, state)

    state.set_state.assert_awaited_once_with(SuggestStates.waiting_recipe_name)
    msg.answer.assert_awaited_once_with("Введите название рецепта:")


async def test_cmd_suggest_collection_closed(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    msg = make_message()
    state = AsyncMock()

    await cmd_suggest(msg, state)

    msg.answer.assert_awaited_once_with("Сбор предложений закрыт.")
    state.set_state.assert_not_awaited()

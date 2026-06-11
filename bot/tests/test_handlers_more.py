"""Тесты хендлеров: /start, /help, /recipes, /suggest (поиск+выбор), /vote (отмена),
/mute, /unmute, /schedule и helpers.check_linked.

Паттерн как в test_handlers.py: AsyncMock/MagicMock + monkeypatch singleton api.
"""
from unittest.mock import AsyncMock, MagicMock, Mock

from app import api_client
from app.api_client import NOT_LINKED_MSG
from app.handlers import menu, notifications, recipes, schedule, start, suggest, vote
from app.helpers import check_linked

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

RECIPES_LIST = [{"id": f"r{i}", "title": f"Рецепт {i}"} for i in range(12)]


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
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.edit_reply_markup = AsyncMock()
    cb.message.delete = AsyncMock()
    return cb


# --- /menu: победитель в закрытом меню ---


async def test_cmd_menu_closed_with_winner(monkeypatch):
    closed_menu = {**MENU_VOTING, "status": "closed", "winner_recipe_id": "r2"}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, closed_menu)))
    msg = make_message()

    await menu.cmd_menu(msg)

    text = msg.answer.await_args.args[0]
    assert "Завершено" in text
    assert "🏆 Победитель: Плов" in text


async def test_cmd_menu_closed_winner_missing(monkeypatch):
    closed_menu = {**MENU_VOTING, "status": "closed", "winner_recipe_id": "ghost"}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, closed_menu)))
    msg = make_message()

    await menu.cmd_menu(msg)

    assert "🏆" not in msg.answer.await_args.args[0]


# --- helpers.check_linked ---


async def test_check_linked_none_answers_and_returns_false():
    msg = make_message()
    assert await check_linked(None, msg) is False
    msg.answer.assert_awaited_once_with(NOT_LINKED_MSG)


async def test_check_linked_ok():
    msg = make_message()
    assert await check_linked(make_response(200), msg) is True
    msg.answer.assert_not_awaited()


# --- /start, /help ---


async def test_cmd_start_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=None))
    msg = make_message()

    await start.cmd_start(msg)

    text = msg.answer.await_args.args[0]
    assert "Добро пожаловать" in text
    assert NOT_LINKED_MSG in text


async def test_cmd_start_linked_first_name(monkeypatch):
    user = {"first_name": "Никита", "username": "telnor"}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, user)))
    msg = make_message()

    await start.cmd_start(msg)

    text = msg.answer.await_args.args[0]
    assert "Привет, Никита!" in text
    assert "/menu" in text


async def test_cmd_start_linked_username_fallback(monkeypatch):
    user = {"first_name": None, "username": "telnor"}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, user)))
    msg = make_message()

    await start.cmd_start(msg)

    assert "Привет, telnor!" in msg.answer.await_args.args[0]


async def test_cmd_help():
    msg = make_message()

    await start.cmd_help(msg)

    msg.answer.assert_awaited_once_with(start.HELP_TEXT)


# --- /mute, /unmute ---


async def test_cmd_mute_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "patch", AsyncMock(return_value=None))
    msg = make_message()

    await notifications.cmd_mute(msg)

    msg.answer.assert_awaited_once_with(NOT_LINKED_MSG)


async def test_cmd_mute_ok(monkeypatch):
    patch_mock = AsyncMock(return_value=make_response(200))
    monkeypatch.setattr(api_client.api, "patch", patch_mock)
    msg = make_message()

    await notifications.cmd_mute(msg)

    patch_mock.assert_awaited_once_with("/api/auth/me", 1, json={"notifications_enabled": False})
    assert "Уведомления отключены" in msg.answer.await_args.args[0]


async def test_cmd_unmute_ok(monkeypatch):
    patch_mock = AsyncMock(return_value=make_response(200))
    monkeypatch.setattr(api_client.api, "patch", patch_mock)
    msg = make_message()

    await notifications.cmd_unmute(msg)

    patch_mock.assert_awaited_once_with("/api/auth/me", 1, json={"notifications_enabled": True})
    assert "Уведомления включены" in msg.answer.await_args.args[0]


async def test_cmd_unmute_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "patch", AsyncMock(return_value=None))
    msg = make_message()

    await notifications.cmd_unmute(msg)

    msg.answer.assert_awaited_once_with(NOT_LINKED_MSG)


# --- /recipes ---


def test_build_recipes_keyboard_first_page():
    kb = recipes.build_recipes_keyboard(RECIPES_LIST, page=0)
    # 10 рецептов + ряд навигации (только ➡️)
    assert len(kb.inline_keyboard) == 11
    nav = kb.inline_keyboard[-1]
    assert [b.text for b in nav] == ["➡️"]
    assert nav[0].callback_data == "recipes_page:1"
    assert kb.inline_keyboard[0][0].callback_data == "recipe:r0"


def test_build_recipes_keyboard_last_page():
    kb = recipes.build_recipes_keyboard(RECIPES_LIST, page=1)
    nav = kb.inline_keyboard[-1]
    assert [b.text for b in nav] == ["⬅️"]
    assert nav[0].callback_data == "recipes_page:0"


def test_build_recipes_keyboard_single_page_no_nav():
    kb = recipes.build_recipes_keyboard(RECIPES_LIST[:3], page=0)
    assert len(kb.inline_keyboard) == 3


def test_format_recipe_full():
    recipe = {
        "title": "Борщ",
        "servings": 4,
        "description": "Классический",
        "ingredients": [
            {"name": "Свёкла", "amount": 2, "unit": "шт"},
            {"name": "Соль", "amount": 1, "unit": None},
        ],
    }
    text = recipes.format_recipe(recipe)
    assert "<b>Борщ</b>" in text
    assert "Порций: 4" in text
    assert "Свёкла — 2 шт" in text
    assert "Соль — 1" in text
    assert "Классический" in text


def test_format_recipe_minimal():
    text = recipes.format_recipe({"title": "Борщ", "servings": 2})
    assert "Ингредиенты" not in text


async def test_cmd_recipes_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=None))
    msg = make_message()

    await recipes.cmd_recipes(msg)

    msg.answer.assert_awaited_once_with(NOT_LINKED_MSG)


async def test_cmd_recipes_empty(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, [])))
    msg = make_message()

    await recipes.cmd_recipes(msg)

    msg.answer.assert_awaited_once_with("Рецептов пока нет.")


async def test_cmd_recipes_ok(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, RECIPES_LIST)))
    msg = make_message()

    await recipes.cmd_recipes(msg)

    assert "📖 Рецепты (12):" in msg.answer.await_args.args[0]
    kb = msg.answer.await_args.kwargs["reply_markup"]
    assert kb.inline_keyboard[0][0].text == "Рецепт 0"


async def test_cb_recipe_detail_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=None))
    cb = make_callback("recipe:r1")

    await recipes.cb_recipe_detail(cb)

    cb.answer.assert_awaited_once_with(NOT_LINKED_MSG)


async def test_cb_recipe_detail_not_found(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(404)))
    cb = make_callback("recipe:r1")

    await recipes.cb_recipe_detail(cb)

    cb.answer.assert_awaited_once_with("Рецепт не найден.")
    cb.message.answer.assert_not_awaited()


async def test_cb_recipe_detail_ok(monkeypatch):
    recipe = {"title": "Борщ", "servings": 4}
    get_mock = AsyncMock(return_value=make_response(200, recipe))
    monkeypatch.setattr(api_client.api, "get", get_mock)
    cb = make_callback("recipe:r1")

    await recipes.cb_recipe_detail(cb)

    get_mock.assert_awaited_once_with("/api/recipes/r1", 1)
    assert "Борщ" in cb.message.answer.await_args.args[0]
    cb.answer.assert_awaited_once_with()


async def test_cb_recipes_page_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=None))
    cb = make_callback("recipes_page:1")

    await recipes.cb_recipes_page(cb)

    cb.answer.assert_awaited_once_with(NOT_LINKED_MSG)
    cb.message.edit_reply_markup.assert_not_awaited()


async def test_cb_recipes_page_ok(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, RECIPES_LIST)))
    cb = make_callback("recipes_page:1")

    await recipes.cb_recipes_page(cb)

    kb = cb.message.edit_reply_markup.await_args.kwargs["reply_markup"]
    assert kb.inline_keyboard[0][0].text == "Рецепт 10"
    cb.answer.assert_awaited_once_with()


# --- /suggest: поиск и выбор ---


async def test_cmd_suggest_menu_not_created(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(404)))
    msg = make_message()
    state = AsyncMock()

    await suggest.cmd_suggest(msg, state)

    msg.answer.assert_awaited_once_with("Меню ещё не создано.")


async def test_on_recipe_name_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=None))
    msg = make_message(text="борщ")
    state = AsyncMock()

    await suggest.on_recipe_name(msg, state)

    msg.answer.assert_awaited_once_with(NOT_LINKED_MSG)
    state.clear.assert_awaited_once()


async def test_on_recipe_name_nothing_found(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, [])))
    msg = make_message(text="суши")
    state = AsyncMock()

    await suggest.on_recipe_name(msg, state)

    state.clear.assert_awaited_once()
    assert "Рецепт не найден" in msg.answer.await_args.args[0]


async def test_on_recipe_name_found_shows_keyboard(monkeypatch):
    found = [{"id": f"r{i}", "title": f"Рецепт {i}"} for i in range(12)]
    get_mock = AsyncMock(return_value=make_response(200, found))
    monkeypatch.setattr(api_client.api, "get", get_mock)
    msg = make_message(text="  борщ  ")
    state = AsyncMock()

    await suggest.on_recipe_name(msg, state)

    get_mock.assert_awaited_once_with("/api/recipes/search?q=борщ", 1)
    state.clear.assert_awaited_once()
    kb = msg.answer.await_args.kwargs["reply_markup"]
    # максимум 10 рецептов + кнопка отмены
    assert len(kb.inline_keyboard) == 11
    assert kb.inline_keyboard[0][0].callback_data == "sug:r0"
    assert kb.inline_keyboard[-1][0].callback_data == "suggest_cancel"


async def test_cb_suggest_menu_not_found(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(404)))
    cb = make_callback("sug:r1")

    await suggest.cb_suggest(cb)

    cb.answer.assert_awaited_once_with("Меню не найдено.")


async def test_cb_suggest_post_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    monkeypatch.setattr(api_client.api, "post", AsyncMock(return_value=None))
    cb = make_callback("sug:r1")

    await suggest.cb_suggest(cb)

    cb.answer.assert_awaited_once_with(NOT_LINKED_MSG)


async def test_cb_suggest_conflict_409(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    monkeypatch.setattr(api_client.api, "post", AsyncMock(return_value=make_response(409)))
    cb = make_callback("sug:r1")

    await suggest.cb_suggest(cb)

    cb.answer.assert_awaited_once_with("Этот рецепт уже в меню.")
    cb.message.delete.assert_awaited_once()


async def test_cb_suggest_bad_request_400(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    monkeypatch.setattr(
        api_client.api,
        "post",
        AsyncMock(return_value=make_response(400, {"detail": "Сбор закрыт"})),
    )
    cb = make_callback("sug:r1")

    await suggest.cb_suggest(cb)

    cb.answer.assert_awaited_once_with("Сбор закрыт")
    cb.message.delete.assert_awaited_once()


async def test_cb_suggest_server_error(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    monkeypatch.setattr(api_client.api, "post", AsyncMock(return_value=make_response(500)))
    cb = make_callback("sug:r1")

    await suggest.cb_suggest(cb)

    cb.answer.assert_awaited_once_with("Ошибка.")
    cb.message.edit_text.assert_not_awaited()


async def test_cb_suggest_success_notifies(monkeypatch):
    updated_menu = {
        **MENU_VOTING,
        "recipes": MENU_VOTING["recipes"] + [{"recipe_id": "r3", "title": "Суп", "votes_count": 0}],
    }
    me = make_response(200, {"first_name": "Никита", "username": "telnor"})

    async def fake_get(path, tg_id, **kwargs):
        if path == "/api/menus/today":
            return make_response(200, MENU_VOTING)
        return me

    post_mock = AsyncMock(return_value=make_response(200, updated_menu))
    monkeypatch.setattr(api_client.api, "get", fake_get)
    monkeypatch.setattr(api_client.api, "post", post_mock)
    notify_mock = AsyncMock()
    monkeypatch.setattr(suggest, "notify_recipe_suggested", notify_mock)
    cb = make_callback("sug:r3")

    await suggest.cb_suggest(cb)

    post_mock.assert_awaited_once_with("/api/menus/m1/suggest", 1, json={"recipe_id": "r3"})
    cb.message.edit_text.assert_awaited_once_with("✅ Суп добавлен в меню!")
    notify_mock.assert_awaited_once_with(cb.bot, "Никита", "Суп", 1)


async def test_cb_suggest_success_unknown_recipe_no_notify(monkeypatch):
    async def fake_get(path, tg_id, **kwargs):
        if path == "/api/menus/today":
            return make_response(200, MENU_VOTING)
        return make_response(500)

    monkeypatch.setattr(api_client.api, "get", fake_get)
    monkeypatch.setattr(api_client.api, "post", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    notify_mock = AsyncMock()
    monkeypatch.setattr(suggest, "notify_recipe_suggested", notify_mock)
    cb = make_callback("sug:rX")

    await suggest.cb_suggest(cb)

    cb.message.edit_text.assert_awaited_once_with("✅ рецепт добавлен в меню!")
    notify_mock.assert_not_awaited()


async def test_cb_suggest_cancel():
    cb = make_callback("suggest_cancel")

    await suggest.cb_suggest_cancel(cb)

    cb.message.delete.assert_awaited_once()
    cb.answer.assert_awaited_once_with("Отменено.")


# --- /vote: дополнительные ветки ---


async def test_cmd_vote_menu_not_created(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(404)))
    msg = make_message()

    await vote.cmd_vote(msg)

    msg.answer.assert_awaited_once_with("Меню ещё не создано.")


async def test_cmd_vote_not_open_yet(monkeypatch):
    menu = {**MENU_VOTING, "status": "collecting"}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, menu)))
    msg = make_message()

    await vote.cmd_vote(msg)

    msg.answer.assert_awaited_once_with("Голосование ещё не открыто.")


async def test_cmd_vote_already_closed(monkeypatch):
    menu = {**MENU_VOTING, "status": "closed"}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, menu)))
    msg = make_message()

    await vote.cmd_vote(msg)

    msg.answer.assert_awaited_once_with("Голосование уже завершено.")


async def test_cmd_vote_already_voted_shows_cancel(monkeypatch):
    menu = {**MENU_VOTING, "user_voted_recipe_id": "r2"}
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, menu)))
    msg = make_message()

    await vote.cmd_vote(msg)

    assert "Ваш голос: Плов ✓" in msg.answer.await_args.args[0]
    kb = msg.answer.await_args.kwargs["reply_markup"]
    callback_data = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert callback_data == ["v:r1", "v:r2", "cancel_vote"]
    texts = [b.text for row in kb.inline_keyboard for b in row]
    assert "Плов ✓" in texts


async def test_cb_vote_menu_not_found(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(404)))
    cb = make_callback("v:r1")

    await vote.cb_vote(cb)

    cb.answer.assert_awaited_once_with("Меню не найдено.")


async def test_cb_vote_post_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    monkeypatch.setattr(api_client.api, "post", AsyncMock(return_value=None))
    cb = make_callback("v:r1")

    await vote.cb_vote(cb)

    cb.answer.assert_awaited_once_with(NOT_LINKED_MSG)


async def test_cb_vote_server_error(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    monkeypatch.setattr(api_client.api, "post", AsyncMock(return_value=make_response(500)))
    cb = make_callback("v:r1")

    await vote.cb_vote(cb)

    cb.answer.assert_awaited_once_with("Ошибка голосования.")


async def test_cb_cancel_vote_menu_not_found(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(404)))
    cb = make_callback("cancel_vote")

    await vote.cb_cancel_vote(cb)

    cb.answer.assert_awaited_once_with("Меню не найдено.")


async def test_cb_cancel_vote_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    monkeypatch.setattr(api_client.api, "delete", AsyncMock(return_value=None))
    cb = make_callback("cancel_vote")

    await vote.cb_cancel_vote(cb)

    cb.answer.assert_awaited_once_with(NOT_LINKED_MSG)
    cb.message.edit_text.assert_not_awaited()


async def test_cb_cancel_vote_ok(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(200, MENU_VOTING)))
    delete_mock = AsyncMock(return_value=make_response(200, MENU_VOTING))
    monkeypatch.setattr(api_client.api, "delete", delete_mock)
    cb = make_callback("cancel_vote")

    await vote.cb_cancel_vote(cb)

    delete_mock.assert_awaited_once_with("/api/menus/m1/vote", 1)
    assert "Голос отменён" in cb.message.edit_text.await_args.args[0]
    cb.answer.assert_awaited_once_with("Голос отменён.")


# --- /schedule ---


async def test_cmd_schedule_not_linked(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=None))
    msg = make_message()

    await schedule.cmd_schedule(msg)

    msg.answer.assert_awaited_once_with(NOT_LINKED_MSG)


async def test_cmd_schedule_auth_error(monkeypatch):
    monkeypatch.setattr(api_client.api, "get", AsyncMock(return_value=make_response(500)))
    msg = make_message()

    await schedule.cmd_schedule(msg)

    msg.answer.assert_awaited_once_with("Ошибка авторизации.")


async def test_cmd_schedule_not_admin(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get", AsyncMock(return_value=make_response(200, {"role": "user"}))
    )
    msg = make_message()

    await schedule.cmd_schedule(msg)

    msg.answer.assert_awaited_once_with("Команда доступна только администраторам.")


async def test_cmd_schedule_admin_ok(monkeypatch):
    monkeypatch.setattr(
        api_client.api, "get", AsyncMock(return_value=make_response(200, {"role": "admin"}))
    )
    monkeypatch.setattr(schedule, "fetch_digest_events", MagicMock(return_value=([], [])))
    msg = make_message()

    await schedule.cmd_schedule(msg)

    text = msg.answer.await_args.args[0]
    assert "Доброе утро" in text
    assert "событий нет" in text

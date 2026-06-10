from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.api_client import NOT_LINKED_MSG, api
from app.callbacks import SUGGEST_CANCEL, SUGGEST_PREFIX, pack, unpack
from app.notify import notify_recipe_suggested

router = Router()


class SuggestStates(StatesGroup):
    waiting_recipe_name = State()


@router.message(Command("suggest"))
async def cmd_suggest(message: Message, state: FSMContext) -> None:
    tg_id = message.from_user.id
    menu, error = await api.get_today_menu(tg_id)

    if error == "not_linked":
        await message.answer(NOT_LINKED_MSG)
        return

    if menu is None:
        await message.answer("Меню ещё не создано.")
        return

    if menu["status"] != "collecting":
        await message.answer("Сбор предложений закрыт.")
        return

    await state.set_state(SuggestStates.waiting_recipe_name)
    await message.answer("Введите название рецепта:")


@router.message(SuggestStates.waiting_recipe_name)
async def on_recipe_name(message: Message, state: FSMContext) -> None:
    tg_id = message.from_user.id
    query = message.text.strip()

    resp = await api.get(f"/api/recipes/search?q={query}", tg_id)
    if resp is None:
        await state.clear()
        await message.answer(NOT_LINKED_MSG)
        return

    recipes = resp.json()
    if not recipes:
        await state.clear()
        await message.answer(
            "Рецепт не найден.\n\nДобавьте его на telnor.ru/recipes/new и попробуйте снова."
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=r["title"],
            callback_data=pack(SUGGEST_PREFIX, r["id"]),
        )]
        for r in recipes[:10]
    ]
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data=SUGGEST_CANCEL)])

    await state.clear()
    await message.answer(
        "Выберите рецепт:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith(SUGGEST_PREFIX))
async def cb_suggest(callback: CallbackQuery) -> None:
    recipe_id = unpack(callback.data, SUGGEST_PREFIX)
    tg_id = callback.from_user.id

    today_menu, _ = await api.get_today_menu(tg_id)
    if today_menu is None:
        await callback.answer("Меню не найдено.")
        return

    menu_id = today_menu["id"]
    resp = await api.post(f"/api/menus/{menu_id}/suggest", tg_id, json={"recipe_id": recipe_id})
    if resp is None:
        await callback.answer(NOT_LINKED_MSG)
        return

    if resp.status_code == 409:
        await callback.answer("Этот рецепт уже в меню.")
        await callback.message.delete()
        return

    if resp.status_code == 400:
        await callback.answer(resp.json().get("detail", "Ошибка"))
        await callback.message.delete()
        return

    if resp.status_code != 200:
        await callback.answer("Ошибка.")
        return

    menu = resp.json()
    suggested = next((r for r in menu["recipes"] if r["recipe_id"] == recipe_id), None)
    title = suggested["title"] if suggested else "рецепт"

    await callback.message.edit_text(f"✅ {title} добавлен в меню!")
    await callback.answer()

    me_resp = await api.get("/api/auth/me", tg_id)
    if me_resp and me_resp.status_code == 200:
        user = me_resp.json()
        name = user.get("first_name") or user["username"]
        await notify_recipe_suggested(callback.bot, name, title, tg_id)


@router.callback_query(F.data == SUGGEST_CANCEL)
async def cb_suggest_cancel(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer("Отменено.")

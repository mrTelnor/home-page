from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.api_client import NOT_LINKED_MSG, api

router = Router()


def build_vote_keyboard(menu: dict) -> InlineKeyboardMarkup:
    user_voted = menu.get("user_voted_recipe_id")
    buttons = []
    for r in menu["recipes"]:
        mark = " ✓" if r["recipe_id"] == user_voted else ""
        buttons.append([InlineKeyboardButton(
            text=f"{r['title']}{mark}",
            callback_data=f"v:{r['recipe_id']}",
        )])
    if user_voted:
        buttons.append([InlineKeyboardButton(
            text="❌ Отменить голос",
            callback_data="cancel_vote",
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("vote"))
async def cmd_vote(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.get("/api/menus/today", tg_id)

    if resp is None:
        await message.answer(NOT_LINKED_MSG)
        return

    if resp.status_code == 404:
        await message.answer("Меню ещё не создано.")
        return

    menu = resp.json()
    if menu["status"] != "voting":
        label = "ещё не открыто" if menu["status"] == "collecting" else "уже завершено"
        await message.answer(f"Голосование {label}.")
        return

    user_voted = menu.get("user_voted_recipe_id")
    if user_voted:
        voted_title = next((r["title"] for r in menu["recipes"] if r["recipe_id"] == user_voted), "?")
        text = f"🗳 Ваш голос: {voted_title} ✓\n\nВыберите другой рецепт или отмените голос:"
    else:
        text = "🗳 Голосование открыто! Выберите рецепт:"

    await message.answer(text, reply_markup=build_vote_keyboard(menu))


@router.callback_query(F.data.startswith("v:"))
async def cb_vote(callback: CallbackQuery) -> None:
    recipe_id = callback.data[2:]
    tg_id = callback.from_user.id

    # Get today's menu for menu_id
    today = await api.get("/api/menus/today", tg_id)
    if today is None or today.status_code != 200:
        await callback.answer("Меню не найдено.")
        return

    menu_id = today.json()["id"]
    resp = await api.post(f"/api/menus/{menu_id}/vote", tg_id, json={"recipe_id": recipe_id})
    if resp is None:
        await callback.answer(NOT_LINKED_MSG)
        return

    if resp.status_code == 409:
        await callback.answer("Вы уже голосовали. Сначала отмените голос.")
        return

    if resp.status_code != 200:
        await callback.answer("Ошибка голосования.")
        return

    menu = resp.json()
    voted_title = next((r["title"] for r in menu["recipes"] if r["recipe_id"] == recipe_id), "?")
    await callback.message.edit_text(
        f"🗳 Ваш голос: {voted_title} ✓\n\nВыберите другой рецепт или отмените голос:",
        reply_markup=build_vote_keyboard(menu),
    )
    await callback.answer("Голос принят!")


@router.callback_query(F.data == "cancel_vote")
async def cb_cancel_vote(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id

    today = await api.get("/api/menus/today", tg_id)
    if today is None or today.status_code != 200:
        await callback.answer("Меню не найдено.")
        return

    menu_id = today.json()["id"]
    resp = await api.delete(f"/api/menus/{menu_id}/vote", tg_id)
    if resp is None:
        await callback.answer(NOT_LINKED_MSG)
        return

    menu = resp.json()
    await callback.message.edit_text(
        "🗳 Голос отменён. Выберите рецепт:",
        reply_markup=build_vote_keyboard(menu),
    )
    await callback.answer("Голос отменён.")

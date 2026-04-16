from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.api_client import NOT_LINKED_MSG, api

router = Router()

PAGE_SIZE = 10


def build_recipes_keyboard(recipes: list[dict], page: int) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_recipes = recipes[start:end]

    buttons = [[InlineKeyboardButton(text=r["title"], callback_data="recipe_noop")] for r in page_recipes]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"recipes_page:{page - 1}"))
    if end < len(recipes):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"recipes_page:{page + 1}"))
    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("recipes"))
async def cmd_recipes(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.get("/api/recipes", tg_id)

    if resp is None:
        await message.answer(NOT_LINKED_MSG)
        return

    recipes = resp.json()
    if not recipes:
        await message.answer("Рецептов пока нет.")
        return

    total = len(recipes)
    await message.answer(
        f"📖 Рецепты ({total}):",
        reply_markup=build_recipes_keyboard(recipes, 0),
    )


@router.callback_query(F.data.startswith("recipes_page:"))
async def cb_recipes_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    tg_id = callback.from_user.id

    resp = await api.get("/api/recipes", tg_id)
    if resp is None:
        await callback.answer(NOT_LINKED_MSG)
        return

    recipes = resp.json()
    await callback.message.edit_reply_markup(reply_markup=build_recipes_keyboard(recipes, page))
    await callback.answer()


@router.callback_query(F.data == "recipe_noop")
async def cb_recipe_noop(callback: CallbackQuery) -> None:
    await callback.answer()

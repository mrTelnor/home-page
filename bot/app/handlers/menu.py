from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.api_client import NOT_LINKED_MSG, api

router = Router()

STATUS_LABELS = {
    "collecting": "Сбор предложений",
    "voting": "Голосование",
    "closed": "Завершено",
}


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.get("/api/menus/today", tg_id)

    if resp is None:
        await message.answer(NOT_LINKED_MSG)
        return

    if resp.status_code == 404:
        await message.answer("Меню ещё не создано.")
        return

    menu = resp.json()
    status_label = STATUS_LABELS.get(menu["status"], menu["status"])
    recipes = "\n".join(f"  • {r['title']}" for r in menu["recipes"])

    text = f"📋 Меню дня ({status_label})\n\n{recipes}"

    if menu["status"] == "closed" and menu.get("winner_recipe_id"):
        winner = next((r for r in menu["recipes"] if r["recipe_id"] == menu["winner_recipe_id"]), None)
        if winner:
            text += f"\n\n🏆 Победитель: {winner['title']}"

    await message.answer(text)

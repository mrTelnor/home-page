import logging

from aiogram import Bot

from app.api_client import api

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "collecting": "Сбор предложений",
    "voting": "Голосование",
    "closed": "Завершено",
}


async def broadcast(bot: Bot, text: str) -> None:
    """Send text to all notifiable users."""
    users = await api.get_notifiable_users()
    for user in users:
        try:
            await bot.send_message(chat_id=user["tg_id"], text=text)
        except Exception:
            logger.warning("Failed to send to tg_id=%s", user["tg_id"])


async def notify_menu_created(bot: Bot) -> None:
    """Notify about new daily menu."""
    users = await api.get_notifiable_users()
    if not users:
        return

    first_tg_id = users[0]["tg_id"]
    resp = await api.get("/api/menus/today", first_tg_id)
    if resp is None or resp.status_code != 200:
        return

    menu = resp.json()
    recipes = "\n".join(f"  • {r['title']}" for r in menu["recipes"])
    text = f"🍽 Меню дня готово! Предлагайте свои варианты.\n\nРецепты:\n{recipes}\n\nИспользуйте /suggest"
    await broadcast(bot, text)


async def notify_voting_opened(bot: Bot) -> None:
    """Notify that voting is open."""
    text = "🗳 Голосование открыто! Используйте /vote для выбора ужина."
    await broadcast(bot, text)


async def notify_voting_closed(bot: Bot) -> None:
    """Notify about voting results."""
    users = await api.get_notifiable_users()
    if not users:
        return

    first_tg_id = users[0]["tg_id"]
    resp = await api.get("/api/menus/today", first_tg_id)
    if resp is None or resp.status_code != 200:
        return

    menu = resp.json()
    winner_id = menu.get("winner_recipe_id")
    results = []
    winner_title = "Не определён"
    for r in sorted(menu["recipes"], key=lambda x: x["votes_count"], reverse=True):
        mark = " 🏆" if r["recipe_id"] == winner_id else ""
        results.append(f"  • {r['title']} — {r['votes_count']} гол.{mark}")
        if r["recipe_id"] == winner_id:
            winner_title = r["title"]

    text = f"🎉 Голосование завершено!\n\nПобедитель: {winner_title}\n\n" + "\n".join(results)
    await broadcast(bot, text)


async def notify_recipe_suggested(bot: Bot, suggester_name: str, recipe_title: str, exclude_tg_id: int) -> None:
    """Notify that someone suggested a recipe."""
    users = await api.get_notifiable_users()
    text = f"📝 {suggester_name} предложил к голосованию: {recipe_title}"
    for user in users:
        if user["tg_id"] == exclude_tg_id:
            continue
        try:
            await bot.send_message(chat_id=user["tg_id"], text=text)
        except Exception:
            logger.warning("Failed to send to tg_id=%s", user["tg_id"])


EVENT_HANDLERS = {
    "menu_created": notify_menu_created,
    "voting_opened": notify_voting_opened,
    "voting_closed": notify_voting_closed,
}

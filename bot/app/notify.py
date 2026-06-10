import logging

from aiogram import Bot

from app.api_client import api
from app.calendar_service import mark_event_sent

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "collecting": "Сбор предложений",
    "voting": "Голосование",
    "closed": "Завершено",
}


async def broadcast(bot: Bot, text: str, *, exclude_admins: bool = False) -> None:
    """Send text to all notifiable users.

    If exclude_admins=True, skip admin users (they receive a richer message
    elsewhere — e.g., as part of the unified morning digest).
    """
    users = await api.get_notifiable_users()
    excluded_ids: set[int] = set()
    if exclude_admins:
        admins = await api.get_admin_users()
        excluded_ids = {a["tg_id"] for a in admins}
    for user in users:
        if user["tg_id"] in excluded_ids:
            continue
        try:
            await bot.send_message(chat_id=user["tg_id"], text=text)
        except Exception:
            logger.warning("Failed to send to tg_id=%s", user["tg_id"])


async def notify_menu_created(bot: Bot) -> None:
    """Notify non-admin users about new daily menu.

    Admins skip this — they get menu info as part of the unified morning
    digest at 09:00 via /check-calendar?digest=true.
    """
    users = await api.get_notifiable_users()
    if not users:
        return

    menu, _ = await api.get_today_menu(users[0]["tg_id"])
    if menu is None:
        return

    recipes = "\n".join(f"  • {r['title']}" for r in menu["recipes"])
    text = f"🍽 Меню дня готово! Предлагайте свои варианты.\n\nРецепты:\n{recipes}\n\nИспользуйте /suggest"
    await broadcast(bot, text, exclude_admins=True)


async def notify_voting_opened(bot: Bot) -> None:
    """Уведомить, что голосование открылось. Идемпотентно: дедуп по id меню."""
    users = await api.get_notifiable_users()
    if not users:
        return
    menu, _ = await api.get_today_menu(users[0]["tg_id"])
    if menu is None:
        return
    if menu.get("status") != "voting":
        return
    if not mark_event_sent(f"voting_opened:{menu['id']}"):
        return

    recipes = menu.get("recipes", [])
    lines = ["🗳 Голосование за ужин открыто!", ""]
    for r in recipes:
        lines.append(f"  • {r['title']}")
    lines.append("")
    lines.append("Голосуй: /vote")
    await broadcast(bot, "\n".join(lines))


async def notify_voting_closed(bot: Bot) -> None:
    """Уведомить о результатах голосования. Идемпотентно: дедуп по id меню."""
    users = await api.get_notifiable_users()
    if not users:
        return

    menu, _ = await api.get_today_menu(users[0]["tg_id"])
    if menu is None:
        return
    if menu.get("status") != "closed":
        return
    if not mark_event_sent(f"voting_closed:{menu['id']}"):
        return
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

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from aiogram.utils.text_decorations import html_decoration

from app.api_client import api
from app.calendar_service import has_event_sent, mark_event_sent
from app.config import settings

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "collecting": "Сбор предложений",
    "voting": "Голосование",
    "closed": "Завершено",
}


async def _send_to_user(bot: Bot, tg_id: int, text: str, extra: dict) -> bool:
    """Отправка одному пользователю.

    True — доставлено, либо доставка невозможна навсегда (пользователь
    заблокировал бота): ретраить такое бессмысленно, иначе catch-up
    будет долбить его каждые 5 минут.
    """
    try:
        await bot.send_message(chat_id=tg_id, text=text, **extra)
        return True
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await bot.send_message(chat_id=tg_id, text=text, **extra)
            return True
        except TelegramAPIError:
            logger.warning("Failed to send to tg_id=%s after flood-control retry", tg_id)
            return False
    except TelegramForbiddenError:
        logger.info("tg_id=%s blocked the bot, not retrying", tg_id)
        return True
    except TelegramAPIError:
        logger.warning("Failed to send to tg_id=%s", tg_id)
        return False


async def broadcast(
    bot: Bot,
    text: str,
    *,
    exclude_admins: bool = False,
    parse_mode: str | None = None,
    dedup_prefix: str | None = None,
) -> None:
    """Send text to all notifiable users.

    If exclude_admins=True, skip admin users (they receive a richer message
    elsewhere — e.g., as part of the unified morning digest).
    parse_mode передаётся в Telegram только когда задан (например, "HTML").

    dedup_prefix включает пер-пользовательский дедуп "{prefix}:{tg_id}":
    маркер ставится ПОСЛЕ успешной отправки, поэтому повторный вызов
    (catch-up из /check-calendar) дошлёт только тем, кому не дошло.
    """
    users = await api.get_notifiable_users()
    excluded_ids: set[int] = set()
    if exclude_admins:
        admins = await api.get_admin_users()
        excluded_ids = {a["tg_id"] for a in admins}
    extra = {"parse_mode": parse_mode} if parse_mode else {}
    for user in users:
        tg_id = user["tg_id"]
        if tg_id in excluded_ids:
            continue
        if dedup_prefix and has_event_sent(f"{dedup_prefix}:{tg_id}"):
            continue
        if await _send_to_user(bot, tg_id, text, extra) and dedup_prefix:
            mark_event_sent(f"{dedup_prefix}:{tg_id}")


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

    # Названия экранируем всегда: у бота глобальный parse_mode=HTML,
    # и сырой "<" в названии рецепта валит отправку у всех получателей.
    recipes = "\n".join(f"  • {html_decoration.quote(r['title'])}" for r in menu["recipes"])
    text = f"🍽 Меню дня готово! Предлагайте свои варианты.\n\nРецепты:\n{recipes}\n\nИспользуйте /suggest"
    await broadcast(bot, text, exclude_admins=True)


async def notify_voting_opened(bot: Bot) -> None:
    """Уведомить, что голосование открылось. Идемпотентно: пер-пользовательский дедуп."""
    users = await api.get_notifiable_users()
    if not users:
        return
    menu, _ = await api.get_today_menu(users[0]["tg_id"])
    if menu is None:
        return
    if menu.get("status") != "voting":
        return
    event_key = f"voting_opened:{menu['id']}"
    # Legacy-маркер (до перехода на пер-пользовательский дедуп): событие уже разослано целиком.
    if has_event_sent(event_key):
        return

    recipes = menu.get("recipes", [])
    lines = ["🗳 Голосование за ужин открыто!", ""]
    for r in recipes:
        lines.append(f"  • {html_decoration.quote(r['title'])}")
    lines.append("")
    lines.append("Голосуй: /vote")
    await broadcast(bot, "\n".join(lines), dedup_prefix=event_key)


async def notify_voting_closed(bot: Bot) -> None:
    """Уведомить о результатах голосования. Идемпотентно: пер-пользовательский дедуп."""
    users = await api.get_notifiable_users()
    if not users:
        return

    menu, _ = await api.get_today_menu(users[0]["tg_id"])
    if menu is None:
        return
    if menu.get("status") != "closed":
        return
    event_key = f"voting_closed:{menu['id']}"
    if has_event_sent(event_key):
        return
    winner_id = menu.get("winner_recipe_id")
    results = []
    winner_html = "Не определён"
    for r in sorted(menu["recipes"], key=lambda x: x["votes_count"], reverse=True):
        is_winner = r["recipe_id"] == winner_id
        mark = " 🏆" if is_winner else ""
        results.append(f"  • {html_decoration.quote(r['title'])} — {r['votes_count']} гол.{mark}")
        if is_winner:
            url = f"{settings.site_url}/recipes/{r['recipe_id']}"
            # link() сам НЕ экранирует текст — прогоняем через quote()
            winner_html = html_decoration.link(html_decoration.quote(r["title"]), url)

    text = f"🎉 Голосование завершено!\n\nПобедитель: {winner_html}\n\n" + "\n".join(results)
    await broadcast(bot, text, parse_mode="HTML", dedup_prefix=event_key)


async def notify_recipe_suggested(bot: Bot, suggester_name: str, recipe_title: str, exclude_tg_id: int) -> None:
    """Notify that someone suggested a recipe."""
    users = await api.get_notifiable_users()
    name = html_decoration.quote(suggester_name)
    title = html_decoration.quote(recipe_title)
    text = f"📝 {name} предложил к голосованию: {title}"
    for user in users:
        if user["tg_id"] == exclude_tg_id:
            continue
        await _send_to_user(bot, user["tg_id"], text, {})


EVENT_HANDLERS = {
    "menu_created": notify_menu_created,
    "voting_opened": notify_voting_opened,
    "voting_closed": notify_voting_closed,
}

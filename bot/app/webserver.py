"""HTTP-endpoints бота (aiohttp): cron-уведомления, аптайм-алерты, календарь.

Поднимается рядом с polling в main.py через create_app(bot).
"""
import asyncio
import hmac
import logging
from datetime import datetime, timedelta

import httpx
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiohttp import web
from aiohttp.abc import AbstractAccessLogger

from app.api_client import api
from app.calendar_service import (
    TZ as CALENDAR_TZ,
)
from app.calendar_service import (
    fetch_digest_events,
    fetch_events,
    format_digest,
    format_single_reminder,
    mark_digest_sent,
    save_sent,
    select_reminders_to_send,
)
from app.config import settings
from app.notify import EVENT_HANDLERS, notify_voting_closed, notify_voting_opened

logger = logging.getLogger(__name__)


def _secret_ok(provided: str | None, expected: str) -> bool:
    """Сравнение секретов в постоянном времени (эндпоинты доступны из интернета)."""
    return provided is not None and hmac.compare_digest(provided, expected)


class NoQueryAccessLogger(AbstractAccessLogger):
    """Access-лог без query string: HetrixTools передаёт секрет как ?secret=...,
    и стандартный формат %r оседал бы вместе с ним в логах."""

    def log(self, request: web.BaseRequest, response: web.StreamResponse, time: float) -> None:
        self.logger.info(
            '%s "%s %s" %s %s %.3fs',
            request.remote,
            request.method,
            request.path,
            response.status,
            response.body_length,
            time,
        )


async def handle_healthz(request: web.Request) -> web.Response:
    """Проверка реальной связности с Telegram (а не только HTTP-сервера).

    Ловит сценарий «polling мёртв, контейнер рестартится»: get_me ходит
    в Telegram API через тот же транспорт, что и polling.
    """
    bot: Bot = request.app["bot"]
    try:
        await bot.get_me()
    except Exception:
        logger.exception("healthz: Telegram unreachable")
        return web.json_response({"status": "error", "detail": "telegram unreachable"}, status=503)
    return web.json_response({"status": "ok"})


async def handle_alert(request: web.Request) -> web.Response:
    """Общий канал алертов для cron: текст рассылается админам."""
    if not _secret_ok(request.headers.get("X-Cron-Secret"), settings.cron_secret):
        return web.json_response({"error": "forbidden"}, status=403)

    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "text is required"}, status=400)

    bot: Bot = request.app["bot"]
    await _send_to_admins(bot, f"⚠️ {text}")
    return web.json_response({"ok": True})


async def handle_notify(request: web.Request) -> web.Response:
    if not _secret_ok(request.headers.get("X-Cron-Secret"), settings.cron_secret):
        return web.json_response({"error": "forbidden"}, status=403)

    data = await request.json()
    event = data.get("event")
    handler = EVENT_HANDLERS.get(event)
    if handler is None:
        return web.json_response({"error": f"unknown event: {event}"}, status=400)

    bot: Bot = request.app["bot"]
    await handler(bot)
    return web.json_response({"ok": True})


async def handle_uptime_alert(request: web.Request) -> web.Response:
    """HetrixTools webhook.

    Секрет — в заголовке X-Uptime-Secret (предпочтительно) либо в ?secret=
    (legacy: query string оседает в логах промежуточных прокси).
    """
    provided = request.headers.get("X-Uptime-Secret") or request.query.get("secret")
    if not _secret_ok(provided, settings.uptime_secret):
        return web.json_response({"error": "forbidden"}, status=403)

    data = await request.json()
    monitor_name = data.get("monitor_name") or data.get("monitor_target") or "unknown"
    monitor_target = data.get("monitor_target", "")
    monitor_status = (data.get("monitor_status") or "").lower()

    if monitor_status == "offline":
        emoji = "🔴"
        status_text = "DOWN"
    elif monitor_status == "online":
        emoji = "🟢"
        status_text = "UP"
    elif monitor_status == "maintenance":
        emoji = "🔧"
        status_text = "MAINTENANCE"
    else:
        emoji = "⚠️"
        status_text = monitor_status or "unknown"

    text = f"{emoji} <b>{monitor_name}</b>: {status_text}"
    if monitor_target and monitor_target != monitor_name:
        text += f"\n{monitor_target}"

    bot: Bot = request.app["bot"]
    await _send_to_admins(bot, text)

    return web.json_response({"ok": True})


async def _send_to_admins(bot: Bot, text: str) -> None:
    admins = await api.get_admin_users()
    for admin in admins:
        try:
            await bot.send_message(chat_id=admin["tg_id"], text=text)
        except TelegramAPIError:
            logger.warning("Failed to send admin message to tg_id=%s", admin["tg_id"])


async def _fetch_today_menu() -> dict | None:
    """Fetch today's menu via API using any admin's tg_id for auth.
    Returns None if no admins are linked or menu not found."""
    admins = await api.get_admin_users()
    if not admins:
        return None
    menu, _ = await api.get_today_menu(admins[0]["tg_id"])
    return menu


async def handle_check_calendar(request: web.Request) -> web.Response:
    """Cron-driven calendar check.

    Query params:
      ?digest=true     — отправить утренний дайджест на сегодня и завтра
      ?force=true      — игнорировать дедупликацию (для дайджеста — отправить
                          даже если уже был сегодня)
    """
    if not _secret_ok(request.headers.get("X-Cron-Secret"), settings.cron_secret):
        return web.json_response({"error": "forbidden"}, status=403)

    bot: Bot = request.app["bot"]
    is_digest = request.query.get("digest") == "true"
    force = request.query.get("force") == "true"

    if is_digest:
        today = datetime.now(CALENDAR_TZ).date()
        if not force and not mark_digest_sent(today):
            return web.json_response({"ok": True, "skipped": "already_sent"})
        # Google API синхронный — в пул потоков, чтобы не морозить polling/healthz
        today_events, tomorrow_events = await asyncio.to_thread(fetch_digest_events)
        menu = await _fetch_today_menu()
        text = format_digest(today_events, tomorrow_events, menu=menu)
        await _send_to_admins(bot, text)
        return web.json_response({
            "ok": True,
            "today": len(today_events),
            "tomorrow": len(tomorrow_events),
            "menu_included": menu is not None,
            "forced": force,
        })

    # Per-event reminders: fetch events in next ~24h, decide which to send now
    now = datetime.now(CALENDAR_TZ)
    time_min = now - timedelta(minutes=5)
    time_max = now + timedelta(hours=25)
    events = await asyncio.to_thread(fetch_events, time_min, time_max)
    reminders, updated_sent = select_reminders_to_send(now, events)
    save_sent(updated_sent)

    for event, label in reminders:
        text = format_single_reminder(event, label)
        await _send_to_admins(bot, text)

    # Catch-up: переопросить статус меню. Если cron-вызов /notify пропал
    # (бот рестартил, сеть моргнула) — досылаем здесь. Дедуп в notify_*
    # гарантирует, что повторного сообщения не будет.
    try:
        await notify_voting_opened(bot)
        await notify_voting_closed(bot)
    except (httpx.HTTPError, TelegramAPIError):
        logger.exception("voting catch-up failed")

    return web.json_response({"ok": True, "sent": len(reminders), "events_fetched": len(events)})


def create_app(bot: Bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/healthz", handle_healthz)
    app.router.add_post("/alert", handle_alert)
    app.router.add_post("/notify", handle_notify)
    app.router.add_post("/uptime-alert", handle_uptime_alert)
    app.router.add_post("/check-calendar", handle_check_calendar)
    return app

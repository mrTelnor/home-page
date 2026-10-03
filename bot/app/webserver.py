"""HTTP-endpoints бота (aiohttp): cron-уведомления, аптайм-алерты, календарь, трекер Vikunja.

Поднимается рядом с polling в main.py через create_app(bot).
"""
import asyncio
import hmac
import json
import logging
from datetime import datetime, time, timedelta

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
    has_event_sent,
    mark_event_sent,
    save_sent,
    select_reminders_to_send,
)
from app.config import settings
from app.notify import (
    EVENT_HANDLERS,
    _send_to_user,
    notify_voting_closed,
    notify_voting_opened,
    wants_calendar,
    wants_dinner,
)
from app.vikunja import build_notifications, signature_ok, user_map

logger = logging.getLogger(__name__)

# Досылка утреннего дайджеста */5-тиком. Начало — после штатной рассылки (cron, 08:00),
# чтобы тик не опередил создание меню; позже полудня «доброе утро» уже не нужно.
DIGEST_CATCHUP_FROM = time(8, 5)
DIGEST_CATCHUP_UNTIL = time(12, 0)
# По умолчанию aiogram ждёт Telegram 60 с — дольше, чем `curl -m 60` в cron.
DIGEST_SEND_TIMEOUT_SEC = 20
# Штатный вызов и тик могут совпасть; маркер ставится после отправки — без замка был бы дубль.
_digest_lock = asyncio.Lock()


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


async def handle_vikunja_webhook(request: web.Request) -> web.Response:
    """Webhook трекера Vikunja: назначение на задачу и новый комментарий.

    Получатель сопоставляется через VIKUNJA_USER_MAP (логин Vikunja → логин сайта),
    tg_id — из /users/tracker-notifiable (флаг «Трекер» в /notifications, /mute
    его тоже выключает). Всё, что не отправляем (чужое событие, логин не в словаре,
    трекер выключен), — 200, чтобы Vikunja не ретраила.
    """
    body = await request.read()
    if not signature_ok(body, request.headers.get("X-Vikunja-Signature"), settings.vikunja_webhook_secret):
        return web.json_response({"error": "invalid signature"}, status=401)

    try:
        payload = json.loads(body)
    except ValueError:
        return web.json_response({"error": "invalid json"}, status=400)
    if not isinstance(payload, dict):
        return web.json_response({"error": "invalid payload"}, status=400)

    notifications = build_notifications(payload)
    if not notifications:
        return web.json_response({"ok": True, "sent": 0})

    logins = user_map()
    tg_by_username = {u["username"]: u["tg_id"] for u in await api.get_tracker_notifiable_users()}
    bot: Bot = request.app["bot"]
    sent = 0
    for vikunja_login, text in notifications:
        site_login = logins.get(vikunja_login)
        if site_login is None:
            logger.info("vikunja: логина %s нет в VIKUNJA_USER_MAP", vikunja_login)
            continue
        tg_id = tg_by_username.get(site_login)
        if tg_id is None:
            logger.info(
                "vikunja: %s (сайт: %s) — трекер выключен или Telegram не привязан",
                vikunja_login, site_login,
            )
            continue
        try:
            await bot.send_message(chat_id=tg_id, text=text)
            sent += 1
        except TelegramAPIError:
            logger.warning("vikunja: не удалось отправить tg_id=%s", tg_id)
    return web.json_response({"ok": True, "sent": sent})


async def _send_to(bot: Bot, recipients: list[dict], text: str) -> None:
    for user in recipients:
        try:
            await bot.send_message(chat_id=user["tg_id"], text=text)
        except TelegramAPIError:
            logger.warning("Failed to send admin message to tg_id=%s", user["tg_id"])


async def _send_to_admins(bot: Bot, text: str) -> None:
    """Системные алерты — всем админам, переключатели уведомлений не действуют."""
    await _send_to(bot, await api.get_admin_users(), text)


async def _fetch_today_menu(admins: list[dict]) -> dict | None:
    """Fetch today's menu via API using any admin's tg_id for auth.
    Returns None if no admins are linked or menu not found."""
    if not admins:
        return None
    menu, _ = await api.get_today_menu(admins[0]["tg_id"])
    return menu


def _digest_catchup_due(now: datetime) -> bool:
    return DIGEST_CATCHUP_FROM <= now.time() < DIGEST_CATCHUP_UNTIL


async def _send_digest(bot: Bot, *, force: bool = False) -> dict:
    """Утренний дайджест тем, кому он сегодня ещё не доставлен.

    Маркер "digest:<дата>:<tg_id>" ставится ПОСЛЕ успешной отправки, поэтому
    повторный вызов (retry в cron, catch-up тиком) дошлёт только тем, кому не дошло.
    """
    async with _digest_lock:
        today = datetime.now(CALENDAR_TZ).date().isoformat()
        admins = await api.get_admin_users()
        # Дайджест — админам с включённым календарём; меню в нём — только тем,
        # у кого включены и ужины (выключившим ужины оно не нужно и в дайджесте).
        recipients = [a for a in admins if wants_calendar(a)]
        if not recipients:
            return {"ok": True, "skipped": "no_recipients"}
        if force:
            pending = recipients
        elif has_event_sent(f"digest:{today}"):
            # Legacy-маркер (до перехода на пер-пользовательский дедуп): разослан целиком.
            pending = []
        else:
            pending = [a for a in recipients if not has_event_sent(f"digest:{today}:{a['tg_id']}")]
        if not pending:
            return {"ok": True, "skipped": "already_sent"}

        # Google API синхронный — в пул потоков, чтобы не морозить polling/healthz
        today_events, tomorrow_events = await asyncio.to_thread(fetch_digest_events)
        menu = await _fetch_today_menu(admins)
        text_with_menu = format_digest(today_events, tomorrow_events, menu=menu)
        text_plain = format_digest(today_events, tomorrow_events)

        async def deliver(user: dict) -> bool:
            text = text_with_menu if wants_dinner(user) else text_plain
            extra = {"request_timeout": DIGEST_SEND_TIMEOUT_SEC}
            if not await _send_to_user(bot, user["tg_id"], text, extra):
                return False
            mark_event_sent(f"digest:{today}:{user['tg_id']}")
            return True

        # Параллельно: при недоступном Telegram ждём один таймаут, а не по одному на получателя
        delivered = await asyncio.gather(*(deliver(u) for u in pending))
        sent = sum(delivered)
        return {
            "ok": sent > 0,
            "today": len(today_events),
            "tomorrow": len(tomorrow_events),
            "menu_included": menu is not None,
            "forced": force,
            "sent": sent,
            "failed": len(pending) - sent,
        }


async def handle_check_calendar(request: web.Request) -> web.Response:
    """Cron-driven calendar check.

    Query params:
      ?digest=true     — отправить утренний дайджест на сегодня и завтра
                          (503, если не доставлен никому)
      ?force=true      — игнорировать дедупликацию (для дайджеста — отправить
                          даже если уже был сегодня)
    """
    if not _secret_ok(request.headers.get("X-Cron-Secret"), settings.cron_secret):
        return web.json_response({"error": "forbidden"}, status=403)

    bot: Bot = request.app["bot"]
    is_digest = request.query.get("digest") == "true"
    force = request.query.get("force") == "true"

    if is_digest:
        result = await _send_digest(bot, force=force)
        # Не дошло никому — 5xx, чтобы curl в cron повторил и поднял алерт.
        # Дошло хотя бы одному — 200: остальным дошлёт тик.
        return web.json_response(result, status=200 if result["ok"] else 503)

    # Per-event reminders: fetch events in next ~24h, decide which to send now
    now = datetime.now(CALENDAR_TZ)
    time_min = now - timedelta(minutes=5)
    time_max = now + timedelta(hours=25)
    events = await asyncio.to_thread(fetch_events, time_min, time_max)
    reminders, updated_sent = select_reminders_to_send(now, events)
    save_sent(updated_sent)

    if reminders:
        recipients = [a for a in await api.get_admin_users() if wants_calendar(a)]
        for event, label in reminders:
            await _send_to(bot, recipients, format_single_reminder(event, label))

    # Catch-up дайджеста: утром Telegram мог быть недоступен — досылаем тем,
    # кому не дошло. Маркер ставится после отправки, дублей не будет.
    if _digest_catchup_due(now):
        try:
            await _send_digest(bot)
        except (httpx.HTTPError, TelegramAPIError):
            logger.exception("digest catch-up failed")

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
    app.router.add_post("/vikunja-webhook", handle_vikunja_webhook)
    return app

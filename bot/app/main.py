import asyncio
import logging
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiohttp import web

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
    mark_digest_sent,
    mark_event_sent,
    save_sent,
    select_reminders_to_send,
)
from app.config import settings
from app.eschool.client import ESchoolClient, EschoolAuthError
from app.eschool.formatters import format_grades_digest, format_homework_digest, format_homework_push
from app.eschool.parser import parse_grades, parse_homework
from app.eschool.service import next_school_day, week_range_ms
from app.handlers import main_router
from app.notify import EVENT_HANDLERS, notify_voting_closed, notify_voting_opened

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="menu", description="Меню дня"),
        BotCommand(command="vote", description="Голосовать за ужин"),
        BotCommand(command="suggest", description="Предложить рецепт"),
        BotCommand(command="recipes", description="Список рецептов"),
        BotCommand(command="schedule", description="Расписание на сегодня и завтра"),
        BotCommand(command="mute", description="Отключить уведомления"),
        BotCommand(command="unmute", description="Включить уведомления"),
        BotCommand(command="help", description="Справка"),
    ])


async def handle_notify(request: web.Request) -> web.Response:
    cron_secret = request.headers.get("X-Cron-Secret")
    if cron_secret != settings.cron_secret:
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
    """HetrixTools webhook. Secret passed as ?secret= query param."""
    if request.query.get("secret") != settings.uptime_secret:
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
    admins = await api.get_admin_users()
    for admin in admins:
        try:
            await bot.send_message(chat_id=admin["tg_id"], text=text)
        except Exception:
            logger.warning("Failed to alert admin tg_id=%s", admin["tg_id"])

    return web.json_response({"ok": True})


async def _send_to_admins(bot: Bot, text: str) -> None:
    admins = await api.get_admin_users()
    for admin in admins:
        try:
            await bot.send_message(chat_id=admin["tg_id"], text=text)
        except Exception:
            logger.warning("Failed to send calendar message to tg_id=%s", admin["tg_id"])


async def _fetch_today_menu() -> dict | None:
    """Fetch today's menu via API using any admin's tg_id for auth.
    Returns None if no admins are linked or menu not found."""
    admins = await api.get_admin_users()
    if not admins:
        return None
    resp = await api.get("/api/menus/today", admins[0]["tg_id"])
    if resp is None or resp.status_code != 200:
        return None
    return resp.json()


async def handle_check_calendar(request: web.Request) -> web.Response:
    """Cron-driven calendar check.

    Query params:
      ?digest=true     — отправить утренний дайджест на сегодня и завтра
      ?force=true      — игнорировать дедупликацию (для дайджеста — отправить
                          даже если уже был сегодня)
    """
    if request.headers.get("X-Cron-Secret") != settings.cron_secret:
        return web.json_response({"error": "forbidden"}, status=403)

    bot: Bot = request.app["bot"]
    is_digest = request.query.get("digest") == "true"
    force = request.query.get("force") == "true"

    if is_digest:
        today = datetime.now(CALENDAR_TZ).date()
        if not force and not mark_digest_sent(today):
            return web.json_response({"ok": True, "skipped": "already_sent"})
        today_events, tomorrow_events = fetch_digest_events()
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
    events = fetch_events(time_min, time_max)
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
    except Exception:
        logger.exception("voting catch-up failed")

    return web.json_response({"ok": True, "sent": len(reminders), "events_fetched": len(events)})


async def _eschool_recipients_for_homework(child_prs_id: int) -> list[int]:
    """Получатели уведомлений о ДЗ: админы-Волковы + сам ученик. tg_id, без дублей."""
    admins = await api.get_eschool_admin_volkovs()
    tg_ids = {a["tg_id"] for a in admins}
    student = await api.get_user_by_eschool_prs_id(child_prs_id)
    if student is not None:
        tg_ids.add(student["tg_id"])
    return list(tg_ids)


async def _eschool_recipients_for_grades() -> list[int]:
    admins = await api.get_eschool_admin_volkovs()
    return [a["tg_id"] for a in admins]


async def _send_to_tg_ids(bot: Bot, tg_ids: list[int], text: str) -> int:
    """Возвращает количество успешно отправленных сообщений."""
    sent = 0
    for tg_id in tg_ids:
        try:
            await bot.send_message(chat_id=tg_id, text=text)
            sent += 1
        except Exception:
            logger.warning("Failed to send eschool message to tg_id=%s", tg_id)
    return sent


async def _alert_eschool_cookies_expired(bot: Bot) -> None:
    """Уведомить админов-Волковых, что cookies eschool протухли — нужно обновить.
    Дедуп — раз в сутки, чтобы не спамить на каждом cron-тике."""
    today_iso = datetime.now(CALENDAR_TZ).date().isoformat()
    if not mark_event_sent(f"eschool_auth_alert:{today_iso}"):
        return
    text = (
        "⚠️ <b>Eschool: cookies протухли</b>\n\n"
        "Дайджесты ДЗ и оценок остановлены до обновления сессии.\n\n"
        "<b>Что делать (≈3 мин):</b>\n"
        "1. Залогиниться на <a href=\"https://app.eschool.center\">app.eschool.center</a>.\n"
        "2. F12 → <b>Network</b> → любой запрос к <code>/ec-server/…</code> → "
        "<b>Request Headers</b> → скопировать значение заголовка <code>Cookie</code> целиком "
        "(строка с <code>JSESSIONID=…; es_prs=…; es_user=…</code>).\n"
        "3. (опционально) Прогнать smoke:\n"
        "<pre>cd bot\npython scripts/check_eschool_cookies.py '&lt;вставить cookie&gt;'</pre>"
        "Ожидаемый вывод: <code>connected ok (cookies_mode=True)</code>.\n"
        "4. Зашифровать и обновить vault:\n"
        "<pre>cd infra/ansible\nansible-vault encrypt_string '&lt;вставить cookie&gt;' --name vault_eschool_cookies</pre>"
        "Заменить блок <code>vault_eschool_cookies</code> в "
        "<code>inventory/group_vars/all/vault.yml</code>.\n"
        "5. Передеплоить bot:\n"
        "<pre>ansible-playbook -i inventory/hosts.yml playbooks/setup.yml --tags bot</pre>\n"
        "Полный runbook: <code>docs/testing.md</code> → «Восстановление cookies eschool»."
    )
    admins = await api.get_eschool_admin_volkovs()
    tg_ids = [a["tg_id"] for a in admins]
    await _send_to_tg_ids(bot, tg_ids, text)


async def handle_check_eschool(request: web.Request) -> web.Response:
    """Cron-driven eschool check.

    Query:
      ?action=homework_digest — дайджест ДЗ на следующий школьный день (15:00 МСК)
      ?action=homework_push   — push новых ДЗ (каждые 30 мин 15:00–22:30)
      ?action=grades_digest   — дайджест оценок за сегодня (18:00 МСК)
      ?force=true             — игнорировать дедуп дайджеста
    """
    if request.headers.get("X-Cron-Secret") != settings.cron_secret:
        return web.json_response({"error": "forbidden"}, status=403)

    eschool: ESchoolClient | None = request.app.get("eschool")
    if eschool is None:
        return web.json_response({"error": "eschool not configured"}, status=503)

    action = request.query.get("action", "")
    force = request.query.get("force") == "true"
    bot: Bot = request.app["bot"]

    child_prs_id = eschool.default_child_prs_id
    if child_prs_id is None:
        return web.json_response({"error": "no child in eschool state"}, status=503)

    today = datetime.now(CALENDAR_TZ).date()

    if action == "homework_digest":
        return await _handle_homework_digest(bot, eschool, child_prs_id, today, force)
    if action == "homework_push":
        return await _handle_homework_push(bot, eschool, child_prs_id, today)
    if action == "grades_digest":
        return await _handle_grades_digest(bot, eschool, child_prs_id, today, force)

    return web.json_response({"error": f"unknown action: {action}"}, status=400)


async def _handle_homework_digest(
    bot: Bot,
    eschool: ESchoolClient,
    child_prs_id: int,
    today: date,
    force: bool,
) -> web.Response:
    digest_key = f"eschool_hw_digest:{child_prs_id}:{today.isoformat()}"
    if not force and has_event_sent(digest_key):
        return web.json_response({"ok": True, "skipped": "already_sent"})

    target_date = next_school_day(today)
    d1, d2 = week_range_ms(target_date)
    try:
        diary = await eschool.get_diary(child_prs_id, d1, d2)
    except EschoolAuthError:
        logger.warning("eschool homework_digest: cookies expired")
        await _alert_eschool_cookies_expired(bot)
        return web.json_response({"error": "auth_expired"}, status=503)
    except Exception:
        logger.exception("eschool homework_digest: fetch failed")
        return web.json_response({"error": "fetch_failed"}, status=502)

    items = parse_homework(diary, target_date)
    if not items:
        return web.json_response({"ok": True, "items": 0, "skipped": "empty"})

    recipients = await _eschool_recipients_for_homework(child_prs_id)
    text = format_homework_digest(items, today=today, target_date=target_date)
    sent = await _send_to_tg_ids(bot, recipients, text)

    if sent > 0:
        mark_event_sent(digest_key)
        for item in items:
            mark_event_sent(f"eschool_hw_lesson:{child_prs_id}:{item.lesson_id}:{item.variant_id}")

    return web.json_response({"ok": True, "items": len(items), "sent": sent})


async def _handle_homework_push(
    bot: Bot,
    eschool: ESchoolClient,
    child_prs_id: int,
    today: date,
) -> web.Response:
    target_date = next_school_day(today)
    d1, d2 = week_range_ms(target_date)
    try:
        diary = await eschool.get_diary(child_prs_id, d1, d2)
    except EschoolAuthError:
        logger.warning("eschool homework_push: cookies expired")
        await _alert_eschool_cookies_expired(bot)
        return web.json_response({"error": "auth_expired"}, status=503)
    except Exception:
        logger.exception("eschool homework_push: fetch failed")
        return web.json_response({"error": "fetch_failed"}, status=502)

    items = parse_homework(diary, target_date)
    truly_new = [
        item for item in items
        if not has_event_sent(f"eschool_hw_lesson:{child_prs_id}:{item.lesson_id}:{item.variant_id}")
    ]

    if not truly_new:
        return web.json_response({"ok": True, "new": 0})

    recipients = await _eschool_recipients_for_homework(child_prs_id)
    text = format_homework_push(truly_new, target_date=target_date)
    sent = await _send_to_tg_ids(bot, recipients, text)

    if sent > 0:
        for item in truly_new:
            mark_event_sent(f"eschool_hw_lesson:{child_prs_id}:{item.lesson_id}:{item.variant_id}")

    return web.json_response({"ok": True, "new": len(truly_new), "sent": sent})


async def _handle_grades_digest(
    bot: Bot,
    eschool: ESchoolClient,
    child_prs_id: int,
    today: date,
    force: bool,
) -> web.Response:
    digest_key = f"eschool_grades_digest:{child_prs_id}:{today.isoformat()}"
    if not force and has_event_sent(digest_key):
        return web.json_response({"ok": True, "skipped": "already_sent"})

    d1, d2 = week_range_ms(today)
    try:
        diary = await eschool.get_diary(child_prs_id, d1, d2)
    except EschoolAuthError:
        logger.warning("eschool grades_digest: cookies expired")
        await _alert_eschool_cookies_expired(bot)
        return web.json_response({"error": "auth_expired"}, status=503)
    except Exception:
        logger.exception("eschool grades_digest: fetch failed")
        return web.json_response({"error": "fetch_failed"}, status=502)

    grades = parse_grades(diary, today)
    if not grades:
        return web.json_response({"ok": True, "grades": 0, "skipped": "empty"})

    recipients = await _eschool_recipients_for_grades()
    text = format_grades_digest(grades, target_date=today)
    sent = await _send_to_tg_ids(bot, recipients, text)

    if sent > 0:
        mark_event_sent(digest_key)
        for g in grades:
            mark_event_sent(f"eschool_grade:{child_prs_id}:{g.mark_id}")

    return web.json_response({"ok": True, "grades": len(grades), "sent": sent})


async def run(bot: Bot, dp: Dispatcher) -> None:
    """Run polling + notify server on the same event loop."""
    # Start HTTP server
    app = web.Application()
    app["bot"] = bot

    # Eschool client (опциональный — endpoint вернёт 503 если клиент не создан).
    # Приоритет режима: cookies > login/password.
    has_cookies = bool(settings.eschool_cookies)
    has_credentials = bool(settings.eschool_login and settings.eschool_password)
    if has_cookies or has_credentials:
        eschool = ESchoolClient(
            base_url=settings.eschool_base_url,
            login=settings.eschool_login,
            password=settings.eschool_password,
            cookie_header=settings.eschool_cookies,
        )
        try:
            await eschool.connect()
            app["eschool"] = eschool
            mode = "cookies" if eschool.cookies_mode else "login/password"
            logger.info(
                "Eschool client connected (%s mode): parent_prs_id=%s, children=%d",
                mode, eschool.parent_prs_id, len(eschool.children),
            )
        except EschoolAuthError:
            logger.warning("Eschool cookies invalid on startup — alerting admins")
            await eschool.aclose()
            app["eschool"] = None
            try:
                await _alert_eschool_cookies_expired(bot)
            except Exception:
                logger.exception("Failed to send eschool cookies-expired alert on startup")
        except Exception:
            logger.exception("Eschool client connect failed — endpoint will return 503")
            await eschool.aclose()
            app["eschool"] = None
    else:
        logger.info("Eschool not configured (no cookies or login/password) — /check-eschool will return 503")
        app["eschool"] = None

    app.router.add_post("/notify", handle_notify)
    app.router.add_post("/uptime-alert", handle_uptime_alert)
    app.router.add_post("/check-calendar", handle_check_calendar)
    app.router.add_post("/check-eschool", handle_check_eschool)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.port)
    await site.start()
    logger.info("Notify server started on port %d", settings.port)

    # Setup bot
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)
    logger.info("Bot started in polling mode")

    # Start polling (blocks until stopped)
    try:
        await dp.start_polling(bot)
    finally:
        if app.get("eschool"):
            await app["eschool"].aclose()
        await runner.cleanup()
        await api.close()
        logger.info("Shutdown complete")


def main() -> None:
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(main_router)
    asyncio.run(run(bot, dp))


if __name__ == "__main__":
    main()

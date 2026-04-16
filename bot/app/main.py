import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.api_client import api
from app.config import settings
from app.handlers import main_router
from app.notify import EVENT_HANDLERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    webhook_url = f"{settings.webhook_host}{settings.webhook_path}"
    for attempt in range(1, 11):
        try:
            await bot.set_webhook(webhook_url)
            logger.info("Webhook set: %s", webhook_url)
            return
        except Exception as e:
            logger.warning("Webhook attempt %d/10 failed: %s", attempt, e)
            if attempt < 10:
                await asyncio.sleep(30)
    logger.error("Failed to set webhook after 10 attempts, starting anyway")


async def on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()
    await api.close()
    logger.info("Shutdown complete")


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


def main() -> None:
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(main_router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app["bot"] = bot

    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=settings.webhook_path)

    app.router.add_post("/notify", handle_notify)

    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()

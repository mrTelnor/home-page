import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiohttp import web

from app.api_client import api
from app.config import settings
from app.handlers import main_router
from app.notify import EVENT_HANDLERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="menu", description="Меню дня"),
        BotCommand(command="vote", description="Голосовать за ужин"),
        BotCommand(command="suggest", description="Предложить рецепт"),
        BotCommand(command="recipes", description="Список рецептов"),
        BotCommand(command="mute", description="Отключить уведомления"),
        BotCommand(command="unmute", description="Включить уведомления"),
        BotCommand(command="help", description="Справка"),
    ])


async def on_startup_polling(bot: Bot) -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)
    logger.info("Bot started in polling mode")


async def on_shutdown_polling(bot: Bot) -> None:
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


async def run_notify_server(bot: Bot) -> None:
    """Run aiohttp server for /notify endpoint alongside polling."""
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/notify", handle_notify)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.port)
    await site.start()
    logger.info("Notify server started on port %d", settings.port)


def main() -> None:
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(main_router)
    dp.startup.register(on_startup_polling)
    dp.shutdown.register(on_shutdown_polling)

    # Start notify server in background, then run polling
    loop = asyncio.new_event_loop()
    loop.run_until_complete(run_notify_server(bot))
    dp.run_polling(bot)


if __name__ == "__main__":
    main()

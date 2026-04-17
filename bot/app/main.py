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


async def run(bot: Bot, dp: Dispatcher) -> None:
    """Run polling + notify server on the same event loop."""
    # Start /notify HTTP server
    app = web.Application()
    app["bot"] = bot
    app.router.add_post("/notify", handle_notify)
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

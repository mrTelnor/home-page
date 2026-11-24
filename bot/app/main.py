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
from app.telegram_relay import TelegramRelaySession
from app.webserver import NoQueryAccessLogger, create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="menu", description="Меню дня"),
        BotCommand(command="vote", description="Голосовать за ужин"),
        BotCommand(command="suggest", description="Предложить рецепт"),
        BotCommand(command="recipes", description="Список рецептов"),
        BotCommand(command="schedule", description="Расписание на сегодня и завтра"),
        BotCommand(command="notifications", description="Настройки уведомлений"),
        BotCommand(command="mute", description="Отключить все уведомления"),
        BotCommand(command="unmute", description="Включить все уведомления"),
        BotCommand(command="help", description="Справка"),
    ])


async def run(bot: Bot, dp: Dispatcher) -> None:
    """Run polling + notify server on the same event loop."""
    runner = web.AppRunner(create_app(bot), access_log_class=NoQueryAccessLogger)
    try:
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", settings.port)
        await site.start()
        logger.info("Notify server started on port %d", settings.port)

        await bot.delete_webhook(drop_pending_updates=True)
        await set_commands(bot)
        logger.info("Bot started in polling mode")

        # Start polling (blocks until stopped)
        await dp.start_polling(bot)
    finally:
        try:
            await runner.cleanup()
        finally:
            try:
                await api.close()
            finally:
                await bot.session.close()
        logger.info("Shutdown complete")


def main() -> None:
    relay_session = TelegramRelaySession(
        relay_url=settings.telegram_relay_url,
        relay_key=settings.telegram_relay_key,
    )

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=relay_session,
    )
    dp = Dispatcher()
    dp.include_router(main_router)
    asyncio.run(run(bot, dp))


if __name__ == "__main__":
    main()

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.api_client import NOT_LINKED_MSG, api
from app.helpers import SERVICE_UNAVAILABLE_MSG

router = Router()

HELP_TEXT = (
    "Команды:\n"
    "/menu — меню дня\n"
    "/vote — голосовать за ужин\n"
    "/suggest — предложить рецепт\n"
    "/recipes — список рецептов\n"
    "/schedule — расписание (для админов)\n"
    "/mute — отключить уведомления\n"
    "/unmute — включить уведомления\n"
    "/help — эта справка"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.get("/api/auth/me", tg_id)

    if resp is None:
        await message.answer(f"Добро пожаловать!\n\n{NOT_LINKED_MSG}")
        return

    if resp.status_code != 200:
        await message.answer(SERVICE_UNAVAILABLE_MSG)
        return

    user = resp.json()
    name = user.get("first_name") or user.get("username") or "друг"
    await message.answer(f"Привет, {name}!\n\n{HELP_TEXT}")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)

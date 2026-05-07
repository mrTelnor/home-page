import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.api_client import NOT_LINKED_MSG, api
from app.calendar_service import fetch_digest_events, format_digest

router = Router()


@router.message(Command("schedule"))
async def cmd_schedule(message: Message) -> None:
    tg_id = message.from_user.id

    me_resp = await api.get("/api/auth/me", tg_id)
    if me_resp is None:
        await message.answer(NOT_LINKED_MSG)
        return

    if me_resp.status_code != 200:
        await message.answer("Ошибка авторизации.")
        return

    user = me_resp.json()
    if user.get("role") != "admin":
        await message.answer("Команда доступна только администраторам.")
        return

    # Google API client is sync — run in thread pool to avoid blocking event loop
    today_events, tomorrow_events = await asyncio.to_thread(fetch_digest_events)
    text = format_digest(today_events, tomorrow_events)
    await message.answer(text)

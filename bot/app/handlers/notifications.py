from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.api_client import api
from app.helpers import check_linked

router = Router()


@router.message(Command("mute"))
async def cmd_mute(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.patch("/api/auth/me", tg_id, json={"notifications_enabled": False})
    if not await check_linked(resp, message):
        return

    await message.answer("🔇 Уведомления отключены. Используйте /unmute чтобы включить.")


@router.message(Command("unmute"))
async def cmd_unmute(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.patch("/api/auth/me", tg_id, json={"notifications_enabled": True})
    if not await check_linked(resp, message):
        return

    await message.answer("🔔 Уведомления включены.")

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.api_client import api
from app.callbacks import NOTIF_PREFIX, pack, unpack
from app.helpers import check_linked, check_ok

router = Router()

# Вид уведомлений → поле профиля в backend
DINNER = "dinner"
CALENDAR = "calendar"
FIELDS = {
    DINNER: "notifications_enabled",
    CALENDAR: "calendar_notifications_enabled",
}

SETTINGS_TEXT = (
    "🔔 Настройки уведомлений\n\n"
    "Нажмите на кнопку, чтобы включить или выключить.\n"
    "/mute и /unmute — все уведомления сразу."
)


def _is_admin(user: dict) -> bool:
    return user.get("role") == "admin"


def _label(title: str, enabled: bool) -> str:
    return f"{title}: {'✅ вкл' if enabled else '🔇 выкл'}"


def build_notifications_keyboard(user: dict) -> InlineKeyboardMarkup:
    """Кнопки-переключатели. Календарь рассылается только админам —
    остальным его кнопка не показывается."""
    buttons = [[InlineKeyboardButton(
        text=_label("🍽 Ужины", user.get(FIELDS[DINNER], True)),
        callback_data=pack(NOTIF_PREFIX, DINNER),
    )]]
    if _is_admin(user):
        buttons.append([InlineKeyboardButton(
            text=_label("📅 Календарь", user.get(FIELDS[CALENDAR], True)),
            callback_data=pack(NOTIF_PREFIX, CALENDAR),
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("notifications"))
async def cmd_notifications(message: Message) -> None:
    resp = await api.get("/api/auth/me", message.from_user.id)
    if not await check_ok(resp, message):
        return

    await message.answer(SETTINGS_TEXT, reply_markup=build_notifications_keyboard(resp.json()))


@router.callback_query(F.data.startswith(NOTIF_PREFIX))
async def cb_toggle_notifications(callback: CallbackQuery) -> None:
    kind = unpack(callback.data, NOTIF_PREFIX)
    field = FIELDS.get(kind)
    if field is None:
        await callback.answer("Неизвестная настройка.")
        return

    tg_id = callback.from_user.id
    # Текущее значение перечитываем: кнопка могла устареть (правка на сайте)
    me_resp = await api.get("/api/auth/me", tg_id)
    if not await check_ok(me_resp, callback):
        return
    user = me_resp.json()
    if kind == CALENDAR and not _is_admin(user):
        await callback.answer("Календарь доступен только администраторам.")
        return

    new_value = not user.get(field, True)
    resp = await api.patch("/api/auth/me", tg_id, json={field: new_value})
    if not await check_ok(resp, callback):
        return

    await callback.message.edit_text(SETTINGS_TEXT, reply_markup=build_notifications_keyboard(resp.json()))
    await callback.answer("Включено." if new_value else "Выключено.")


@router.message(Command("mute"))
async def cmd_mute(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.patch("/api/auth/me", tg_id, json={field: False for field in FIELDS.values()})
    if not await check_linked(resp, message):
        return

    await message.answer(
        "🔇 Все уведомления отключены. /unmute — включить всё, /notifications — выбрать отдельно."
    )


@router.message(Command("unmute"))
async def cmd_unmute(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.patch("/api/auth/me", tg_id, json={field: True for field in FIELDS.values()})
    if not await check_linked(resp, message):
        return

    await message.answer("🔔 Все уведомления включены. /notifications — выбрать отдельно.")

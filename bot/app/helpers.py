from aiogram.types import CallbackQuery, Message

from app.api_client import NOT_LINKED_MSG

SERVICE_UNAVAILABLE_MSG = "Сервис временно недоступен, попробуйте позже."


async def check_linked(resp: object | None, target: Message | CallbackQuery) -> bool:
    """False + ответ NOT_LINKED_MSG, если запрос вернул None (аккаунт не привязан).

    Для Message отправляет сообщение, для CallbackQuery — toast (метод answer
    есть у обоих).
    """
    if resp is None:
        await target.answer(NOT_LINKED_MSG)
        return False
    return True


async def check_ok(resp: object | None, target: Message | CallbackQuery) -> bool:
    """True только при resp со статусом 200. None → NOT_LINKED_MSG,
    иначе (backend вернул 4xx/5xx) → общая ошибка. Уберегает от resp.json()
    без проверки статуса (KeyError на неожиданном теле)."""
    if resp is None:
        await target.answer(NOT_LINKED_MSG)
        return False
    if getattr(resp, "status_code", None) != 200:
        await target.answer(SERVICE_UNAVAILABLE_MSG)
        return False
    return True

from aiogram.types import CallbackQuery, Message

from app.api_client import NOT_LINKED_MSG


async def check_linked(resp: object | None, target: Message | CallbackQuery) -> bool:
    """False + ответ NOT_LINKED_MSG, если запрос вернул None (аккаунт не привязан).

    Для Message отправляет сообщение, для CallbackQuery — toast (метод answer
    есть у обоих).
    """
    if resp is None:
        await target.answer(NOT_LINKED_MSG)
        return False
    return True

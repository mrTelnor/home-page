"""Константы и helpers для callback_data inline-кнопок.

Wire-формат зафиксирован (кнопки в уже отправленных сообщениях продолжают
работать после деплоя) — менять префиксы нельзя без миграции старых сообщений.
"""

VOTE_PREFIX = "v:"
SUGGEST_PREFIX = "sug:"
RECIPE_PREFIX = "recipe:"
RECIPES_PAGE_PREFIX = "recipes_page:"
CANCEL_VOTE = "cancel_vote"
SUGGEST_CANCEL = "suggest_cancel"


def pack(prefix: str, value: str | int) -> str:
    return f"{prefix}{value}"


def unpack(data: str, prefix: str) -> str:
    """Достать полезную нагрузку из callback_data с известным префиксом."""
    return data[len(prefix):]

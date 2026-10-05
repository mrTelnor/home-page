"""Подключение к базе знаний (Supabase) для вики — только чтение.

Отдельный engine, не связанный с основной БД сайта:
- ходим ролью `wiki_reader` через пулер Supabase в session-режиме (порт 5432),
  поэтому кэш подготовленных запросов asyncpg отключать не нужно;
- engine создаётся лениво — при пустом `WIKI_DATABASE_URL` вики выключена,
  а backend стартует и работает без Supabase;
- у роли connection limit 6, а при пересоздании контейнера старый и новый пулы
  живут одновременно — поэтому `pool_size + max_overflow` не больше 3;
- SSL обязателен, но в строке подключения его нет — задаём здесь.
"""
import logging
import re
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from urllib.parse import unquote

import asyncpg
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

WIKI_POOL_SIZE = 2
WIKI_MAX_OVERFLOW = 1
# Ожидание свободного соединения из пула, секунды
WIKI_POOL_TIMEOUT = 5
# Пересоздавать соединения старше 5 минут: пулер и NAT рвут простаивающие
WIKI_POOL_RECYCLE = 300
# Таймаут установки соединения (asyncpg `timeout`), секунды
WIKI_CONNECT_TIMEOUT = 5
# Таймаут запроса на стороне клиента (asyncpg `command_timeout`), секунды.
# Чуть больше серверного statement_timeout = 5s роли wiki_reader: штатно запрос
# обрывает сервер, клиентский таймаут — страховка на случай зависшей сети.
WIKI_COMMAND_TIMEOUT = 8


class WikiDisabledError(Exception):
    """Вики выключена: `WIKI_DATABASE_URL` пуст."""


class WikiUnavailableError(Exception):
    """База знаний недоступна: нет связи, пауза проекта Supabase, таймаут, ошибка запроса."""


# OSError покрывает отказ в соединении и таймауты (TimeoutError — его подкласс).
# Исключения asyncpg перечислены отдельно: при установке соединения SQLAlchemy
# не всегда оборачивает их в свои (неверный пароль, «tenant not found» пулера).
_DB_ERRORS = (SQLAlchemyError, OSError, asyncpg.PostgresError, asyncpg.InterfaceError)

_engine: AsyncEngine | None = None


def get_wiki_engine() -> AsyncEngine:
    """Вернуть engine базы знаний, создав его при первом обращении."""
    global _engine
    if not settings.wiki_database_url:
        raise WikiDisabledError
    if _engine is None:
        _engine = create_async_engine(
            settings.wiki_database_url,
            pool_size=WIKI_POOL_SIZE,
            max_overflow=WIKI_MAX_OVERFLOW,
            pool_timeout=WIKI_POOL_TIMEOUT,
            pool_pre_ping=True,
            pool_recycle=WIKI_POOL_RECYCLE,
            connect_args={
                # Аналог sslmode=require: шифрование без проверки сертификата
                "ssl": "require",
                "timeout": WIKI_CONNECT_TIMEOUT,
                "command_timeout": WIKI_COMMAND_TIMEOUT,
            },
        )
    return _engine


_URL_PASSWORD_RE = re.compile(r"://[^:/@]*:([^@]*)@")


def _safe_error_text(exc: BaseException) -> str:
    """Текст исключения для лога без строки подключения и пароля.

    Ошибки разбора URL и драйвера могут цитировать исходную строку целиком.
    """
    message = f"{type(exc).__name__}: {exc}"
    url = settings.wiki_database_url
    if not url:
        return message
    secrets = [url]
    match = _URL_PASSWORD_RE.search(url)
    if match and match.group(1):
        secrets += [match.group(1), unquote(match.group(1))]
    for secret in secrets:
        message = message.replace(secret, "***")
    return message


@asynccontextmanager
async def wiki_connection() -> AsyncGenerator[AsyncConnection, None]:
    """Соединение с базой знаний.

    Любой сбой превращается в `WikiUnavailableError`; детали — только в лог,
    наружу они не уходят. Две фазы:
    - создание engine и подключение — ловим всё: кривая строка подключения даёт
      не только ошибки БД (ModuleNotFoundError, ValueError, TypeError);
    - работа с соединением — только ошибки БД: исключения самого эндпоинта
      (например, 404) проходят через этот блок и должны остаться как есть.
    """
    try:
        async with AsyncExitStack() as stack:
            try:
                engine = get_wiki_engine()
                conn = await stack.enter_async_context(engine.connect())
            except WikiDisabledError:
                raise
            except Exception as exc:
                # Без трассировки и с вычищенным текстом: в сообщении может быть строка подключения
                logger.error("Wiki database request failed (connect): %s", _safe_error_text(exc))
                raise WikiUnavailableError from None
            yield conn
    except _DB_ERRORS as exc:
        logger.exception("Wiki database request failed")
        raise WikiUnavailableError from exc


async def dispose_wiki_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None

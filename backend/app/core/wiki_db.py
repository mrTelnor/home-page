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
import asyncio
import logging
import re
import time
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Literal
from urllib.parse import unquote

import asyncpg
from sqlalchemy import text
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
# Сколько секунд публичный health отвечает из памяти, не обращаясь к базе
WIKI_HEALTH_CACHE_TTL = 10
# Пока база недоступна, запись о сбое проверки health повторяется в логе не чаще, секунды
WIKI_HEALTH_LOG_INTERVAL = 300
# Текст ошибки в записи о сбое проверки health обрезается до этой длины
WIKI_HEALTH_ERROR_MAX_LENGTH = 300

WikiHealthStatus = Literal["ok", "unavailable", "disabled"]


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


# --- Проверка связи для публичного health ---
#
# Health открыт всем и не ограничен лимитом, поэтому в базу ходит не каждый запрос:
# результат проверки живёт в памяти процесса WIKI_HEALTH_CACHE_TTL секунд, а пока
# проверка идёт, все пришедшие запросы ждут её одну. Так health занимает не больше
# одного соединения из пула. Backend работает одним воркером — памяти процесса хватает.

# Последний результат проверки и момент, когда он получен (по _monotonic)
_health_cache: tuple[WikiHealthStatus, float] | None = None
# Проверка, которая идёт прямо сейчас
_health_task: asyncio.Task[WikiHealthStatus] | None = None
# Когда о недоступности базы в последний раз писали в лог; None — база не считалась недоступной
_health_failure_logged_at: float | None = None


def _monotonic() -> float:
    """Часы кэша health. Отдельная функция, чтобы тесты подменяли время, не трогая часы event loop."""
    return time.monotonic()


async def _probe_wiki() -> tuple[WikiHealthStatus, str | None]:
    """Один `select 1` в базе знаний: статус и, при сбое, короткий текст ошибки для лога.

    Идёт мимо `wiki_connection`: тот пишет в лог сам и с трассировкой, а здесь запись
    делает вызывающий и не на каждую проверку. Исключений эндпоинта тут нет, поэтому
    любой сбой — «недоступна».
    """
    try:
        engine = get_wiki_engine()
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
    except WikiDisabledError:
        return "disabled", None
    except Exception as exc:
        # Одна строка: у ошибок SQLAlchemy текст многострочный (запрос, ссылка на справку)
        message = " ".join(_safe_error_text(exc).split())
        return "unavailable", message[:WIKI_HEALTH_ERROR_MAX_LENGTH]
    return "ok", None


def _log_health(status: WikiHealthStatus, error: str | None) -> None:
    """Запись в лог: при переходе в «недоступна» и затем не чаще WIKI_HEALTH_LOG_INTERVAL."""
    global _health_failure_logged_at
    if status == "unavailable":
        now = _monotonic()
        if _health_failure_logged_at is None or now - _health_failure_logged_at >= WIKI_HEALTH_LOG_INTERVAL:
            logger.error("Wiki health check failed: %s", error)
            _health_failure_logged_at = now
        return
    if status == "ok" and _health_failure_logged_at is not None:
        logger.info("Wiki health check: database is available again")
    _health_failure_logged_at = None


async def _refresh_wiki_health() -> WikiHealthStatus:
    """Одна проверка базы знаний: запись в лог, обновление кэша, по завершении — снятие себя из `_health_task`."""
    global _health_cache, _health_task
    try:
        status, error = await _probe_wiki()
        _log_health(status, error)
        # «Выключена» не кэшируем: это состояние в базу не ходит, беречь нечего
        if status != "disabled":
            # Окно отсчитывается от конца проверки: медленный сбой (таймаут) не съедает его
            _health_cache = (status, _monotonic())
        return status
    finally:
        if _health_task is asyncio.current_task():
            _health_task = None


async def get_wiki_health() -> WikiHealthStatus:
    """Статус базы знаний для health: из кэша, а при пустом или истёкшем — одной общей проверкой."""
    global _health_task
    if _health_cache is not None and _monotonic() - _health_cache[1] < WIKI_HEALTH_CACHE_TTL:
        return _health_cache[0]
    # done(): задача, отменённая до первого шага, не доходит до своего finally и сама себя не убирает
    if _health_task is None or _health_task.done():
        _health_task = asyncio.create_task(_refresh_wiki_health())
    # shield: отмена одного из ждущих запросов не обрывает проверку для остальных
    return await asyncio.shield(_health_task)


def reset_wiki_health_cache() -> None:
    """Забыть результат проверки health (остановка приложения, тесты)."""
    global _health_cache, _health_task, _health_failure_logged_at
    _health_cache = None
    _health_task = None
    _health_failure_logged_at = None


async def dispose_wiki_engine() -> None:
    global _engine
    reset_wiki_health_cache()
    if _engine is not None:
        await _engine.dispose()
        _engine = None

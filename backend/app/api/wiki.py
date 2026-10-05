"""Вики: просмотр базы знаний (Supabase) — только чтение, только для админов.

Все эндпоинты, кроме health, требуют роль admin. Проверка прав стоит зависимостью
роутера и выполняется раньше обращения к базе знаний: гость получает 401,
а не 503, даже когда Supabase недоступен.
"""
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.dependencies import get_admin_user
from app.core.ratelimit import WIKI_LIMIT, limiter
from app.core.wiki_db import WikiDisabledError, WikiUnavailableError, get_wiki_health, wiki_connection
from app.schemas.wiki import WikiHealthResponse, WikiNotebookNode, WikiNoteDetail, WikiNoteSummary
from app.services import wiki as wiki_service

router = APIRouter(prefix="/wiki", tags=["wiki"])

WIKI_DISABLED = "Wiki is disabled"
WIKI_UNAVAILABLE = "Wiki database is unavailable"
NOTEBOOK_NOT_FOUND = "Notebook not found"
NOTE_NOT_FOUND = "Note not found"

# Один счётчик на IP для всех эндпоинтов вики (кроме health)
WIKI_LIMIT_SCOPE = "wiki"

SEARCH_LIMIT_DEFAULT = 20
RECENT_LIMIT_DEFAULT = 20
LIST_LIMIT_MAX = 50
SEARCH_QUERY_MAX_LENGTH = 200
FILTER_MAX_LENGTH = 100
# Нулевой байт Postgres в тексте не принимает: запрос упал бы и дал 503 вместо отказа по вводу
NO_NUL_PATTERN = r"^[^\x00]*$"


@limiter.shared_limit(WIKI_LIMIT, scope=WIKI_LIMIT_SCOPE)
async def wiki_rate_limit(request: Request) -> None:
    """Общий лимит вики. Тела нет: всю работу делает декоратор slowapi.

    Подключён зависимостью роутера, а не декоратором эндпоинтов: так он срабатывает
    раньше проверки прав и считает в том числе запросы гостей.
    """


# Всё, кроме health: сначала лимит, потом проверка роли admin
admin_router = APIRouter(dependencies=[Depends(wiki_rate_limit), Depends(get_admin_user)])


async def get_wiki_conn() -> AsyncGenerator[AsyncConnection, None]:
    """Соединение с базой знаний; выключенная вики и сбой базы → 503 с понятным detail."""
    try:
        async with wiki_connection() as conn:
            yield conn
    except WikiDisabledError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=WIKI_DISABLED) from None
    except WikiUnavailableError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=WIKI_UNAVAILABLE) from None


WikiConn = Annotated[AsyncConnection, Depends(get_wiki_conn)]


@router.get("/health", response_model=WikiHealthResponse)
async def health():
    """Публичная проверка связи с базой знаний: всегда 200 и только статус.

    Пауза Supabase не должна валить smoke-тест деплоя, поэтому не 503.
    Лимита нет, поэтому в базу ходит не каждый запрос: результат проверки
    кэшируется на несколько секунд (см. `get_wiki_health`).
    """
    return {"status": await get_wiki_health()}


@admin_router.get("/notebooks", response_model=list[WikiNotebookNode])
async def notebooks(conn: WikiConn):
    """Дерево блокнотов со счётчиками заметок."""
    return await wiki_service.get_notebook_tree(conn)


@admin_router.get("/notebooks/{notebook_id}/notes", response_model=list[WikiNoteSummary])
async def notebook_notes(notebook_id: uuid.UUID, conn: WikiConn):
    """Заметки блокнота (без вложенных блокнотов)."""
    notes = await wiki_service.get_notebook_notes(conn, notebook_id)
    if notes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOTEBOOK_NOT_FOUND)
    return notes


@admin_router.get("/search", response_model=list[WikiNoteSummary])
async def search(
    conn: WikiConn,
    q: Annotated[str | None, Query(max_length=SEARCH_QUERY_MAX_LENGTH)] = None,
    project: Annotated[str | None, Query(max_length=FILTER_MAX_LENGTH, pattern=NO_NUL_PATTERN)] = None,
    note_type: Annotated[str | None, Query(alias="type", max_length=FILTER_MAX_LENGTH, pattern=NO_NUL_PATTERN)] = None,
    tag: Annotated[str | None, Query(max_length=FILTER_MAX_LENGTH, pattern=NO_NUL_PATTERN)] = None,
    limit: Annotated[int, Query(ge=1, le=LIST_LIMIT_MAX)] = SEARCH_LIMIT_DEFAULT,
):
    """Поиск по началу слов с фильтрами по metadata.project, metadata.type и тегу."""
    return await wiki_service.search_notes(conn, q, project, note_type, tag, limit)


@admin_router.get("/recent", response_model=list[WikiNoteSummary])
async def recent(
    conn: WikiConn,
    limit: Annotated[int, Query(ge=1, le=LIST_LIMIT_MAX)] = RECENT_LIMIT_DEFAULT,
):
    """Последние изменённые заметки."""
    return await wiki_service.get_recent_notes(conn, limit)


# slug заметки содержит «/» (moi-domashnii-sait/grabli) — поэтому :path
@admin_router.get("/notes/{slug:path}", response_model=WikiNoteDetail)
async def note(slug: str, conn: WikiConn):
    """Заметка по slug: текст, metadata, теги, исходящие и обратные ссылки."""
    # slug с нулевым байтом существовать не может — до базы его не доводим
    if "\x00" in slug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOTE_NOT_FOUND)
    result = await wiki_service.get_note_by_slug(conn, slug)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOTE_NOT_FOUND)
    return result


router.include_router(admin_router)

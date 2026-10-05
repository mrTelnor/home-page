"""Чтение базы знаний (Supabase) для вики.

Все запросы — только SELECT и только с параметрами: пользовательский ввод
в текст SQL не попадает. Текст запроса собирается из фиксированных фрагментов.
"""
import json
import re
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# Слово для поиска — буквы и цифры любого алфавита; всё остальное (включая «_»
# и операторы tsquery & | ! ( ) : * < >) — разделитель.
_WORD_RE = re.compile(r"[^\W_]+")
# Больше слов в одном запросе не берём — лишние отбрасываются
MAX_SEARCH_WORDS = 8

# Теги заметки одним массивом; '{}' — когда тегов нет
_TAGS_SQL = """
    coalesce(
        (select array_agg(t.name order by t.name)
           from note_tags nt
           join tags t on t.id = nt.tag_id
          where nt.note_id = n.id),
        '{}'
    ) as tags
"""

_SUMMARY_COLUMNS = f"n.id, n.slug, n.title, n.notebook_id, n.metadata, n.updated_at, {_TAGS_SQL}"


def build_tsquery(q: str | None) -> str | None:
    """Собрать строку для to_tsquery('simple', …): каждое слово — префикс, между словами AND.

    «Грабли home-page!» → «грабли:* & home:* & page:*». Если слов нет — None.
    """
    if not q:
        return None
    words = _WORD_RE.findall(q.lower())[:MAX_SEARCH_WORDS]
    if not words:
        return None
    return " & ".join(f"{word}:*" for word in words)


def _metadata(value: Any) -> dict[str, Any]:
    """jsonb из сырого запроса asyncpg отдаёт строкой — приводим к словарю."""
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, dict) else {}


def _summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "notebook_id": row["notebook_id"],
        "metadata": _metadata(row["metadata"]),
        "tags": list(row["tags"] or []),
        "updated_at": row["updated_at"],
    }


def build_notebook_tree(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Собрать дерево блокнотов из плоского списка и посчитать заметки с учётом вложенных.

    Блокнот, чей родитель не найден, считается корневым.
    """
    nodes: dict[uuid.UUID, dict[str, Any]] = {
        row["id"]: {
            "id": row["id"],
            "name": row["name"],
            "slug": row["slug"],
            "parent_id": row["parent_id"],
            "note_count": row["note_count"],
            "total_note_count": row["note_count"],
            "children": [],
        }
        for row in rows
    }
    roots: list[dict[str, Any]] = []
    for node in nodes.values():
        parent = nodes.get(node["parent_id"]) if node["parent_id"] is not None else None
        if parent is None or parent is node:
            roots.append(node)
        else:
            parent["children"].append(node)

    def fill_totals(node: dict[str, Any]) -> int:
        node["total_note_count"] = node["note_count"] + sum(fill_totals(child) for child in node["children"])
        return node["total_note_count"]

    for root in roots:
        fill_totals(root)
    return roots


async def get_notebook_tree(conn: AsyncConnection) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(
            """
            select nb.id, nb.name, nb.slug, nb.parent_id,
                   (select count(*) from notes n where n.notebook_id = nb.id) as note_count
              from notebooks nb
             order by nb.name
            """
        )
    )
    return build_notebook_tree(list(result.mappings().all()))


async def get_notebook_notes(conn: AsyncConnection, notebook_id: uuid.UUID) -> list[dict[str, Any]] | None:
    """Заметки непосредственно в блокноте (без вложенных). None — блокнота нет."""
    exists = await conn.execute(text("select 1 from notebooks where id = :notebook_id"), {"notebook_id": notebook_id})
    if exists.first() is None:
        return None
    result = await conn.execute(
        text(f"select {_SUMMARY_COLUMNS} from notes n where n.notebook_id = :notebook_id order by n.slug"),
        {"notebook_id": notebook_id},
    )
    return [_summary(row) for row in result.mappings().all()]


async def get_note_by_slug(conn: AsyncConnection, slug: str) -> dict[str, Any] | None:
    result = await conn.execute(
        text(
            f"""
            select n.id, n.slug, n.title, n.content, n.metadata, n.created_at, n.updated_at,
                   nb.id as notebook_id, nb.name as notebook_name, nb.slug as notebook_slug,
                   {_TAGS_SQL}
              from notes n
              left join notebooks nb on nb.id = n.notebook_id
             where n.slug = :slug
            """
        ),
        {"slug": slug},
    )
    row = result.mappings().first()
    if row is None:
        return None

    links = await conn.execute(
        text(
            """
            select t.slug, t.title, l.alias
              from note_links l
              join notes t on t.id = l.target_note_id
             where l.source_note_id = :note_id
             order by t.title, l.alias
            """
        ),
        {"note_id": row["id"]},
    )
    backlinks = await conn.execute(
        text(
            """
            select source_slug as slug, source_title as title, alias
              from backlinks_view
             where target_id = :note_id
             order by source_title, alias
            """
        ),
        {"note_id": row["id"]},
    )

    notebook = None
    if row["notebook_id"] is not None:
        notebook = {"id": row["notebook_id"], "name": row["notebook_name"], "slug": row["notebook_slug"]}
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "content": row["content"],
        "metadata": _metadata(row["metadata"]),
        "notebook": notebook,
        "tags": list(row["tags"] or []),
        "links": [dict(link) for link in links.mappings().all()],
        "backlinks": [dict(link) for link in backlinks.mappings().all()],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def search_notes(
    conn: AsyncConnection,
    q: str | None,
    project: str | None,
    note_type: str | None,
    tag: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Поиск по search_vector (конфиг simple, префикс слова) с фильтрами.

    Без слов в запросе работает как список по фильтрам; без слов и без фильтров — пусто.
    """
    tsquery = build_tsquery(q)
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit}

    if tsquery is not None:
        conditions.append("n.search_vector @@ to_tsquery('simple', :tsquery)")
        params["tsquery"] = tsquery
    if project:
        conditions.append("n.metadata ->> 'project' = :project")
        params["project"] = project
    if note_type:
        conditions.append("n.metadata ->> 'type' = :note_type")
        params["note_type"] = note_type
    if tag:
        conditions.append(
            "exists (select 1 from note_tags ft join tags ftg on ftg.id = ft.tag_id"
            " where ft.note_id = n.id and ftg.name = :tag)"
        )
        params["tag"] = tag

    if not conditions:
        return []

    if tsquery is not None:
        order_by = "ts_rank(n.search_vector, to_tsquery('simple', :tsquery)) desc, n.updated_at desc"
    else:
        order_by = "n.updated_at desc"

    # В текст запроса попадают только фрагменты из этого модуля, значения — параметрами
    result = await conn.execute(
        text(
            f"select {_SUMMARY_COLUMNS} from notes n"
            f" where {' and '.join(conditions)}"
            f" order by {order_by} limit :limit"
        ),
        params,
    )
    return [_summary(row) for row in result.mappings().all()]


async def get_recent_notes(conn: AsyncConnection, limit: int) -> list[dict[str, Any]]:
    result = await conn.execute(
        text(f"select {_SUMMARY_COLUMNS} from notes n order by n.updated_at desc limit :limit"),
        {"limit": limit},
    )
    return [_summary(row) for row in result.mappings().all()]

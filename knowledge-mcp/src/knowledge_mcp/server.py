"""MCP server exposing knowledge base to Claude Desktop via stdio.

9 tools, each thin wrapper around KnowledgeClient. Errors from PostgREST
propagate as exceptions — the MCP framework reports them to the client.
"""
from __future__ import annotations

import asyncio
import json

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

from knowledge_mcp.auth import TokenManager
from knowledge_mcp.client import KnowledgeClient
from knowledge_mcp.config import Settings


def _ret(obj) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(obj, ensure_ascii=False, default=str))]


def build_server(client: KnowledgeClient | None = None) -> FastMCP:
    """Build MCP server. In tests pass a pre-built client; in prod main() creates one from env."""
    if client is None:
        s = Settings()
        tm = TokenManager(backend_url=s.backend_url, username=s.username, password=s.password)
        client = KnowledgeClient(base_url=s.url, token_manager=tm, timeout=s.timeout_seconds)

    server = FastMCP("knowledge-mcp")

    @server.tool()
    async def list_notebooks() -> list[TextContent]:
        """Все ноутбуки (id/name/slug/parent_id), отсортированы по slug."""
        return _ret(await client.list_notebooks())

    @server.tool()
    async def create_notebook(name: str, slug: str,
                              parent_id: str | None = None) -> list[TextContent]:
        """Создать новый ноутбук (папку). parent_id — UUID родительского ноутбука или None."""
        return _ret(await client.create_notebook(name=name, slug=slug, parent_id=parent_id))

    @server.tool()
    async def search_notes(query: str, limit: int = 20) -> list[TextContent]:
        """Полнотекстовый поиск по заметкам (Postgres FTS, simple config — работает с RU/EN)."""
        return _ret(await client.search_notes(query=query, limit=limit))

    @server.tool()
    async def get_note(slug: str | None = None,
                       id: str | None = None) -> list[TextContent]:
        """Получить заметку (с content и metadata) по slug или id. Одно из двух обязательно."""
        if not slug and not id:
            return _ret({"error": "either slug or id required"})
        return _ret(await client.get_note(slug=slug, id=id))

    @server.tool()
    async def list_notes(notebook_slug: str | None = None,
                         limit: int = 50, offset: int = 0) -> list[TextContent]:
        """Список заметок (без content). Опционально фильтр по notebook_slug."""
        return _ret(await client.list_notes(notebook_slug=notebook_slug,
                                              limit=limit, offset=offset))

    @server.tool()
    async def create_note(notebook_id: str, title: str, slug: str,
                          content: str = "",
                          metadata: dict | None = None) -> list[TextContent]:
        """Создать заметку в указанном ноутбуке."""
        return _ret(await client.create_note(notebook_id=notebook_id, title=title,
                                               slug=slug, content=content, metadata=metadata))

    @server.tool()
    async def update_note(id: str, content: str | None = None,
                          title: str | None = None,
                          metadata: dict | None = None) -> list[TextContent]:
        """Обновить заметку. Передавай только те поля, что меняешь."""
        return _ret(await client.update_note(id=id, content=content,
                                               title=title, metadata=metadata))

    @server.tool()
    async def delete_note(id: str) -> list[TextContent]:
        """Удалить заметку (без подтверждения)."""
        await client.delete_note(id=id)
        return [TextContent(type="text", text="deleted")]

    @server.tool()
    async def get_backlinks(target_slug: str) -> list[TextContent]:
        """Все заметки, ссылающиеся на target_slug (через note_links)."""
        return _ret(await client.get_backlinks(target_slug=target_slug))

    return server


def main() -> None:
    """Entry point — `knowledge-mcp` CLI command from pyproject.toml scripts."""
    asyncio.run(build_server().run_stdio_async())

import httpx
import pytest
import respx

from knowledge_mcp.auth import TokenManager
from knowledge_mcp.client import KnowledgeClient


def make_tm(token: str = "tok") -> TokenManager:
    tm = TokenManager(backend_url="https://backend", username="u", password="p")
    tm._token = token
    return tm


@respx.mock
async def test_list_notebooks():
    respx.get("https://knowledge/notebooks").mock(return_value=httpx.Response(
        200, json=[{"id": "nb1", "name": "Personal", "slug": "personal"}]
    ))
    client = KnowledgeClient(base_url="https://knowledge", token_manager=make_tm())
    rows = await client.list_notebooks()
    assert rows[0]["slug"] == "personal"


@respx.mock
async def test_search_notes_uses_fts():
    respx.get("https://knowledge/notes").mock(return_value=httpx.Response(
        200, json=[{"id": "n1", "title": "Found", "slug": "x/found"}]
    ))
    client = KnowledgeClient(base_url="https://knowledge", token_manager=make_tm())
    rows = await client.search_notes(query="hello", limit=10)
    assert len(rows) == 1
    assert "fts" in str(respx.calls.last.request.url)


@respx.mock
async def test_get_note_by_slug_returns_none_on_empty():
    respx.get("https://knowledge/notes").mock(return_value=httpx.Response(200, json=[]))
    client = KnowledgeClient(base_url="https://knowledge", token_manager=make_tm())
    assert await client.get_note(slug="missing") is None


@respx.mock
async def test_get_note_by_slug_returns_row():
    respx.get("https://knowledge/notes").mock(return_value=httpx.Response(
        200, json=[{"id": "n1", "title": "Hello", "slug": "nb/hello"}]
    ))
    client = KnowledgeClient(base_url="https://knowledge", token_manager=make_tm())
    note = await client.get_note(slug="nb/hello")
    assert note["title"] == "Hello"


@respx.mock
async def test_update_note():
    respx.patch("https://knowledge/notes").mock(return_value=httpx.Response(
        200, json=[{"id": "n1", "title": "Updated", "slug": "x/n", "content": "new body"}]
    ))
    client = KnowledgeClient(base_url="https://knowledge", token_manager=make_tm())
    note = await client.update_note(id="n1", content="new body")
    assert note["content"] == "new body"


@respx.mock
async def test_get_backlinks():
    respx.get("https://knowledge/backlinks_view").mock(return_value=httpx.Response(
        200, json=[{"source_slug": "a", "source_title": "A", "alias": None}]
    ))
    client = KnowledgeClient(base_url="https://knowledge", token_manager=make_tm())
    rows = await client.get_backlinks(target_slug="b")
    assert rows[0]["source_slug"] == "a"

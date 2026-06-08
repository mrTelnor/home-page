"""Async PostgREST client with all CRUD + FTS + backlinks."""
from __future__ import annotations

import httpx

from knowledge_mcp.auth import TokenManager


class KnowledgeClient:
    def __init__(self, *, base_url: str, token_manager: TokenManager,
                 timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._tm = token_manager
        self._http = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _req(self, method: str, path: str, **kwargs) -> httpx.Response:
        token = await self._tm.token()
        headers = kwargs.pop("headers", {})
        headers = {**headers, "Authorization": f"Bearer {token}"}
        resp = await self._http.request(method, f"{self._base_url}{path}",
                                          headers=headers, **kwargs)
        if resp.status_code == 401:
            token = await self._tm.token(force_refresh=True)
            headers["Authorization"] = f"Bearer {token}"
            resp = await self._http.request(method, f"{self._base_url}{path}",
                                              headers=headers, **kwargs)
        resp.raise_for_status()
        return resp

    # -------- Notebooks --------

    async def list_notebooks(self) -> list[dict]:
        return (await self._req("GET", "/notebooks", params={"order": "slug"})).json()

    async def create_notebook(self, *, name: str, slug: str,
                              parent_id: str | None = None) -> dict:
        body = {"name": name, "slug": slug, "parent_id": parent_id}
        resp = await self._req("POST", "/notebooks", json=body,
                                 headers={"Prefer": "return=representation",
                                          "Content-Type": "application/json"})
        return resp.json()[0]

    # -------- Notes --------

    async def search_notes(self, *, query: str, limit: int = 20) -> list[dict]:
        return (await self._req("GET", "/notes", params={
            "search_vector": f"fts(simple).{query}",
            "select": "id,title,slug,notebook_id,updated_at",
            "limit": str(limit),
        })).json()

    async def list_notes(self, *, notebook_slug: str | None = None,
                         limit: int = 50, offset: int = 0) -> list[dict]:
        params = {"select": "id,title,slug,notebook_id,updated_at",
                  "order": "updated_at.desc",
                  "limit": str(limit), "offset": str(offset)}
        if notebook_slug:
            params["notebooks.slug"] = f"eq.{notebook_slug}"
            params["select"] = "id,title,slug,notebook_id,updated_at,notebooks!inner()"
        return (await self._req("GET", "/notes", params=params)).json()

    async def get_note(self, *, slug: str | None = None,
                       id: str | None = None) -> dict | None:
        params: dict[str, str] = {"limit": "1"}
        if slug:
            params["slug"] = f"eq.{slug}"
        elif id:
            params["id"] = f"eq.{id}"
        else:
            return None
        rows = (await self._req("GET", "/notes", params=params)).json()
        return rows[0] if rows else None

    async def create_note(self, *, notebook_id: str, title: str, slug: str,
                          content: str = "", metadata: dict | None = None) -> dict:
        body = {"notebook_id": notebook_id, "title": title, "slug": slug,
                "content": content, "metadata": metadata or {}}
        resp = await self._req("POST", "/notes", json=body,
                                 headers={"Prefer": "return=representation",
                                          "Content-Type": "application/json"})
        return resp.json()[0]

    async def update_note(self, *, id: str,
                          content: str | None = None,
                          title: str | None = None,
                          metadata: dict | None = None) -> dict:
        body = {k: v for k, v in
                {"content": content, "title": title, "metadata": metadata}.items()
                if v is not None}
        resp = await self._req("PATCH", f"/notes?id=eq.{id}", json=body,
                                 headers={"Prefer": "return=representation",
                                          "Content-Type": "application/json"})
        return resp.json()[0]

    async def delete_note(self, *, id: str) -> None:
        await self._req("DELETE", f"/notes?id=eq.{id}")

    # -------- Backlinks --------

    async def get_backlinks(self, *, target_slug: str) -> list[dict]:
        return (await self._req("GET", "/backlinks_view", params={
            "target_slug": f"eq.{target_slug}",
            "select": "source_slug,source_title,alias",
        })).json()

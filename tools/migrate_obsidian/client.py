"""Async PostgREST client with TokenManager-driven auth and 401-retry."""
from __future__ import annotations

import httpx

from migrate_obsidian.auth import TokenManager


class PostgRESTClient:
    def __init__(self, *, base_url: str, token_manager: TokenManager,
                 timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._tm = token_manager
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"Content-Type": "application/json", "Prefer": "return=representation"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
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

    async def create_notebook(self, *, name: str, slug: str,
                              parent_id: str | None = None) -> dict:
        body = {"name": name, "slug": slug, "parent_id": parent_id}
        resp = await self._request("POST", "/notebooks", json=body)
        return resp.json()[0]

    async def ensure_tag(self, name: str) -> str:
        # PostgREST upsert requires explicit on_conflict for non-PK unique columns.
        resp = await self._request(
            "POST", "/tags?on_conflict=name", json={"name": name},
            headers={"Prefer": "resolution=merge-duplicates,return=representation"},
        )
        return resp.json()[0]["id"]

    async def attach_tags(self, *, note_id: str, tag_names: list[str]) -> None:
        if not tag_names:
            return
        tag_ids = [await self.ensure_tag(n) for n in tag_names]
        rows = [{"note_id": note_id, "tag_id": tid} for tid in tag_ids]
        await self._request(
            "POST", "/note_tags?on_conflict=note_id,tag_id", json=rows,
            headers={"Prefer": "resolution=ignore-duplicates"},
        )

    async def create_note(self, *, notebook_id: str, title: str, slug: str,
                          content: str = "", metadata: dict | None = None,
                          tags: list[str] | None = None) -> dict:
        body = {
            "notebook_id": notebook_id, "title": title, "slug": slug,
            "content": content, "metadata": metadata or {},
        }
        resp = await self._request("POST", "/notes", json=body)
        note = resp.json()[0]
        if tags:
            await self.attach_tags(note_id=note["id"], tag_names=tags)
        return note

    async def create_link(self, *, source_id: str, target_id: str,
                          alias: str | None = None) -> None:
        await self._request(
            "POST", "/note_links?on_conflict=source_note_id,target_note_id,alias",
            json={"source_note_id": source_id, "target_note_id": target_id,
                  "alias": alias},
            headers={"Prefer": "resolution=ignore-duplicates"},
        )

"""TokenManager: get JWT from backend by login/password, cache, refresh on demand."""
from __future__ import annotations

import asyncio

import httpx


class TokenManager:
    """Gets JWT from backend's /api/auth/knowledge-token endpoint and caches it.
    Refresh by calling token(force_refresh=True)."""

    def __init__(self, *, backend_url: str, username: str, password: str,
                 timeout: float = 10.0) -> None:
        self._backend_url = backend_url.rstrip("/")
        self._username = username
        self._password = password
        self._http = httpx.AsyncClient(timeout=timeout)
        self._token: str | None = None
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def token(self, *, force_refresh: bool = False) -> str:
        async with self._lock:
            if self._token is None or force_refresh:
                resp = await self._http.post(
                    f"{self._backend_url}/api/auth/knowledge-token",
                    json={"username": self._username, "password": self._password},
                )
                resp.raise_for_status()
                self._token = resp.json()["access_token"]
            return self._token

"""HTTP-клиент для eschool с cookie-сессией и авто-релогином."""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class ESchoolClient:
    """Cookie-сессия к app.eschool.center/ec-server.

    Использование:
        client = ESchoolClient(login=..., password=...)
        await client.connect()
        diary = await client.get_diary(prs_id=..., d1_ms=..., d2_ms=...)
        await client.aclose()

    На 401/403 автоматически перелогинивается и повторяет запрос один раз.
    """

    def __init__(self, login: str, password: str, base_url: str) -> None:
        self._login = login
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"User-Agent": "Mozilla/5.0 (compatible; HomePageBot)"},
        )
        self.parent_prs_id: int | None = None
        self.children: list[dict] = []
        self._connected = False

    async def aclose(self) -> None:
        await self._http.aclose()

    async def connect(self) -> None:
        """Залогиниться и подгрузить state. Бросает исключение при ошибке."""
        await self._do_login()
        await self._load_state()
        self._connected = True

    async def _do_login(self) -> None:
        resp = await self._http.post("/login", json={"login": self._login, "pass": self._password})
        resp.raise_for_status()

    async def _load_state(self) -> None:
        resp = await self._http.get("/state")
        resp.raise_for_status()
        state = resp.json()
        position = state["user"]["currentPosition"]
        self.parent_prs_id = position.get("prsId")
        self.children = position.get("myChildren") or []

    @property
    def default_child_prs_id(self) -> int | None:
        if not self.children:
            return None
        return self.children[0]["prsId"]

    async def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        resp = await self._http.request(method, path, **kwargs)
        if resp.status_code in (401, 403):
            logger.info("eschool session expired (status=%s), re-logging in", resp.status_code)
            await self._do_login()
            resp = await self._http.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp

    async def get_diary(self, prs_id: int, d1_ms: int, d2_ms: int) -> dict:
        resp = await self._request_with_retry(
            "GET",
            "/student/getPrsDiary",
            params={"prsId": prs_id, "d1": d1_ms, "d2": d2_ms},
        )
        return resp.json()

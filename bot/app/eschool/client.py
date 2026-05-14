"""HTTP-клиент для eschool с cookie-сессией.

Два режима авторизации:
1. Manual cookies — `cookie_header` строкой из браузера. Бот не пытается логиниться
   (login через /ec-server/login блокируется reCAPTCHA). При 401/403 бросаем
   EschoolAuthError — handler в main.py отправляет алерт админу: «обнови cookies».
2. Login/password — оставлено как fallback на случай если eschool снимет reCAPTCHA
   или мы перейдём на Playwright. Сейчас в боевом профиле не работает.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class EschoolAuthError(Exception):
    """Сессия eschool протухла или невалидна. В cookie-режиме повторно
    залогиниться нельзя, нужно обновить cookies вручную."""


class ESchoolClient:
    """Cookie-сессия к app.eschool.center/ec-server.

    Usage (cookies mode, рекомендуется):
        client = ESchoolClient(cookie_header="JSESSIONID=...; es_prs=...")
        await client.connect()  # проверит /state с этими куками
        diary = await client.get_diary(prs_id=..., d1_ms=..., d2_ms=...)
        await client.aclose()

    Usage (login/pass mode, fallback):
        client = ESchoolClient(login="user", password="pass")
        await client.connect()  # сейчас падает на капче
    """

    def __init__(
        self,
        base_url: str,
        login: str = "",
        password: str = "",
        cookie_header: str = "",
    ) -> None:
        self._login = login
        self._password = password
        self._cookie_header = cookie_header.strip()
        self._base_url = base_url.rstrip("/")
        headers = {
            # Реальный Chrome-UA — eschool возвращает 503 на «бот»-агенты типа `compatible; XBot`.
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if self._cookie_header:
            headers["Cookie"] = self._cookie_header
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers=headers,
        )
        self.parent_prs_id: int | None = None
        self.children: list[dict] = []
        self._connected = False

    @property
    def cookies_mode(self) -> bool:
        return bool(self._cookie_header)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def connect(self) -> None:
        """Установить сессию. В cookies-режиме только верифицирует /state.
        Бросает EschoolAuthError если cookies невалидны или login не прошёл."""
        if self.cookies_mode:
            logger.info("eschool: cookies mode, verifying session via /state")
        else:
            await self._do_login()
        await self._load_state()
        self._connected = True

    async def _do_login(self) -> None:
        resp = await self._http.post("/login", json={"login": self._login, "pass": self._password})
        resp.raise_for_status()

    async def _load_state(self) -> None:
        resp = await self._http.get("/state")
        if resp.status_code in (401, 403):
            raise EschoolAuthError(f"state returned {resp.status_code}")
        resp.raise_for_status()
        state = resp.json()
        if not state.get("authenticated"):
            raise EschoolAuthError("state.authenticated is false")
        position = state["user"]["currentPosition"]
        self.parent_prs_id = position.get("prsId")
        self.children = position.get("myChildren") or []

    @property
    def default_child_prs_id(self) -> int | None:
        if not self.children:
            return None
        return self.children[0].get("prsId")

    async def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        resp = await self._http.request(method, path, **kwargs)
        if resp.status_code in (401, 403):
            if self.cookies_mode:
                raise EschoolAuthError(
                    f"{method} {path} returned {resp.status_code} — cookies expired"
                )
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

import httpx

from app.config import settings

NOT_LINKED_MSG = "Привяжите Telegram-аккаунт на telnor.ru/profile, затем попробуйте снова."


class ApiClient:
    def __init__(self) -> None:
        self._tokens: dict[int, str] = {}
        self._http = httpx.AsyncClient(base_url=settings.backend_url, timeout=10)

    async def close(self) -> None:
        await self._http.aclose()

    async def login(self, tg_id: int) -> str | None:
        """Get JWT for a Telegram user. Returns None if user not linked."""
        resp = await self._http.post(
            "/api/auth/telegram-login",
            json={"tg_id": tg_id},
            headers={"X-Bot-Secret": settings.bot_secret},
        )
        if resp.status_code == 404:
            self._tokens.pop(tg_id, None)
            return None
        resp.raise_for_status()
        token = resp.json()["access_token"]
        self._tokens[tg_id] = token
        return token

    async def _get_token(self, tg_id: int) -> str | None:
        if tg_id in self._tokens:
            return self._tokens[tg_id]
        return await self.login(tg_id)

    async def request(self, method: str, path: str, tg_id: int, **kwargs) -> httpx.Response | None:
        """Make authenticated request. Returns None if user not linked."""
        token = await self._get_token(tg_id)
        if token is None:
            return None

        headers = {"Authorization": f"Bearer {token}"}
        resp = await self._http.request(method, path, headers=headers, **kwargs)

        if resp.status_code == 401:
            token = await self.login(tg_id)
            if token is None:
                return None
            headers = {"Authorization": f"Bearer {token}"}
            resp = await self._http.request(method, path, headers=headers, **kwargs)

        return resp

    async def get(self, path: str, tg_id: int, **kwargs) -> httpx.Response | None:
        return await self.request("GET", path, tg_id, **kwargs)

    async def post(self, path: str, tg_id: int, **kwargs) -> httpx.Response | None:
        return await self.request("POST", path, tg_id, **kwargs)

    async def patch(self, path: str, tg_id: int, **kwargs) -> httpx.Response | None:
        return await self.request("PATCH", path, tg_id, **kwargs)

    async def delete(self, path: str, tg_id: int, **kwargs) -> httpx.Response | None:
        return await self.request("DELETE", path, tg_id, **kwargs)

    async def get_notifiable_users(self) -> list[dict]:
        resp = await self._http.get(
            "/api/auth/users/notifiable",
            headers={"X-Bot-Secret": settings.bot_secret},
        )
        resp.raise_for_status()
        return resp.json()


api = ApiClient()

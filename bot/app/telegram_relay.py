from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlsplit

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramServerError
from aiogram.methods.base import TelegramType
from aiohttp import ClientError

if TYPE_CHECKING:
    from aiogram.client.bot import Bot
    from aiogram.methods import TelegramMethod


def _origin(url: str) -> tuple[str, str | None, int | None]:
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    port = parsed.port
    if port is None:
        port = {"http": 80, "https": 443}.get(scheme)
    hostname = parsed.hostname
    return scheme, hostname.lower() if hostname else None, port


class TelegramRelaySession(AiohttpSession):
    """Сессия aiogram, отправляющая Bot API-запросы через Cloudflare Worker."""

    def __init__(self, relay_url: str, relay_key: str, **kwargs: Any) -> None:
        relay_url = relay_url.rstrip("/")
        api = TelegramAPIServer(
            base=f"{relay_url}/{{method}}",
            # Worker не поддерживает файловые методы и отклонит такой путь.
            file=f"{relay_url}/file/{{path}}",
        )
        super().__init__(api=api, **kwargs)
        self._relay_key = relay_key
        self._relay_origin = _origin(relay_url)

    def _headers_for_url(self, url: str, headers: dict[str, Any] | None = None) -> dict[str, Any]:
        request_headers = {
            name: value for name, value in (headers or {}).items() if name.lower() != "x-relay-key"
        }
        if _origin(url) == self._relay_origin:
            request_headers["X-Relay-Key"] = self._relay_key
        return request_headers

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        session = await self.create_session()
        url = self.api.api_url(token=bot.token, method=method.__api_method__)
        form = self.build_form_data(bot=bot, method=method)
        # Без файлов aiohttp выбирает urlencoded, а Worker принимает только JSON или multipart.
        form._is_multipart = True

        try:
            async with session.post(
                url,
                data=form,
                timeout=self.timeout if timeout is None else timeout,
                headers=self._headers_for_url(url),
                allow_redirects=False,
            ) as resp:
                raw_result = await resp.text()
        except TimeoutError as e:
            raise TelegramNetworkError(method=method, message="Request timeout error") from e
        except ClientError as e:
            raise TelegramNetworkError(method=method, message=f"{type(e).__name__}: {e}") from e
        if resp.status >= 400:
            try:
                error_data = self.json_loads(raw_result)
            except ValueError:
                error_data = None
            if (
                isinstance(error_data, dict)
                and error_data.get("ok") is False
                and isinstance(error_data.get("error"), str)
            ):
                error_class = TelegramServerError if resp.status >= 500 else TelegramAPIError
                raise error_class(method=method, message=error_data["error"])

        response = self.check_response(
            bot=bot,
            method=method,
            status_code=resp.status,
            content=raw_result,
        )
        return cast(TelegramType, response.result)

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        session = await self.create_session()
        async with session.get(
            url,
            timeout=timeout,
            headers=self._headers_for_url(url, headers),
            raise_for_status=raise_for_status,
            allow_redirects=False,
        ) as resp:
            async for chunk in resp.content.iter_chunked(chunk_size):
                yield chunk

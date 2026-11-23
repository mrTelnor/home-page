import json
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.methods import (
    AnswerCallbackQuery,
    DeleteMessage,
    EditMessageReplyMarkup,
    EditMessageText,
    GetUpdates,
    SendMessage,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiohttp import FormData
from multidict import CIMultiDict
from pydantic import ValidationError

from app.config import Settings
from app.telegram_relay import TelegramRelaySession

BOT_TOKEN = "123456:test-token"
RELAY_URL = "https://relay.example.test"
RELAY_KEY = "test-relay-key"
MESSAGE_RESULT = {
    "message_id": 10,
    "date": 0,
    "chat": {"id": 42, "type": "private"},
}


class FakeResponse:
    def __init__(self, status: int, content: str) -> None:
        self.status = status
        self._content = content

    async def text(self) -> str:
        return self._content


class FakeRequestContext:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    async def __aenter__(self) -> FakeResponse:
        return self.response

    async def __aexit__(self, *args) -> None:
        return None


class FakeClientSession:
    def __init__(self, status: int = 200, result=None, error: Exception | None = None) -> None:
        self.status = status
        self.result = result
        self.error = error
        self.requests = []

    def post(self, url, *, data, timeout, headers, allow_redirects) -> FakeRequestContext:
        self.requests.append(
            {
                "url": url,
                "data": data,
                "timeout": timeout,
                "headers": headers,
                "allow_redirects": allow_redirects,
            },
        )
        if self.error is not None:
            raise self.error
        content = json.dumps({"ok": self.status == 200, "result": self.result})
        return FakeRequestContext(FakeResponse(self.status, content))


class BodyWriter:
    def __init__(self) -> None:
        self.body = bytearray()

    async def write(self, chunk: bytes) -> None:
        self.body.extend(chunk)


def make_bot_and_http_session(monkeypatch, **http_kwargs):
    relay_session = TelegramRelaySession(RELAY_URL, RELAY_KEY)
    http_session = FakeClientSession(**http_kwargs)
    monkeypatch.setattr(relay_session, "create_session", AsyncMock(return_value=http_session))
    return Bot(token=BOT_TOKEN, session=relay_session), http_session


async def serialize_form(form: FormData) -> tuple[str, bytes]:
    payload = form()
    writer = BodyWriter()
    await payload.write(writer)
    return payload.headers["Content-Type"], bytes(writer.body)


@pytest.mark.parametrize(
    ("method", "method_name", "result", "expected_type"),
    [
        (GetUpdates(timeout=10), "getUpdates", [], list),
        (SendMessage(chat_id=42, text="hello"), "sendMessage", MESSAGE_RESULT, Message),
        (
            EditMessageText(chat_id=42, message_id=10, text="updated"),
            "editMessageText",
            MESSAGE_RESULT,
            Message,
        ),
        (
            EditMessageReplyMarkup(
                chat_id=42,
                message_id=10,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="OK", callback_data="ok")]],
                ),
            ),
            "editMessageReplyMarkup",
            MESSAGE_RESULT,
            Message,
        ),
        (DeleteMessage(chat_id=42, message_id=10), "deleteMessage", True, bool),
        (AnswerCallbackQuery(callback_query_id="callback-id"), "answerCallbackQuery", True, bool),
    ],
)
async def test_methods_use_relay_and_preserve_aiogram_results(
    monkeypatch,
    method,
    method_name,
    result,
    expected_type,
):
    bot, http_session = make_bot_and_http_session(monkeypatch, result=result)

    response = await bot(method)

    assert isinstance(response, expected_type)
    request = http_session.requests[0]
    assert request["url"] == f"{RELAY_URL}/{method_name}"
    assert BOT_TOKEN not in request["url"]
    assert "api.telegram.org" not in request["url"]
    assert request["headers"] == {"X-Relay-Key": RELAY_KEY}
    assert request["timeout"] == bot.session.timeout
    assert request["allow_redirects"] is False
    assert isinstance(request["data"], FormData)

    content_type, body = await serialize_form(request["data"])
    assert content_type.startswith("multipart/form-data; boundary=")
    assert b"filename=" not in body


async def test_multipart_contains_worker_compatible_fields(monkeypatch):
    bot, http_session = make_bot_and_http_session(monkeypatch, result=MESSAGE_RESULT)
    reply_markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="OK", callback_data="ok")]],
    )

    await bot(SendMessage(chat_id=42, text="hello", parse_mode="HTML", reply_markup=reply_markup))

    _, body = await serialize_form(http_session.requests[0]["data"])
    assert b'name="chat_id"' in body
    assert b'name="text"' in body
    assert b'name="parse_mode"' in body
    assert b'name="reply_markup"' in body
    assert b'"callback_data": "ok"' in body


@pytest.mark.parametrize(
    ("status", "content", "expected_exception"),
    [
        (
            429,
            {
                "ok": False,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 7},
            },
            TelegramRetryAfter,
        ),
        (400, {"ok": False, "description": "Bad Request"}, TelegramBadRequest),
    ],
)
async def test_telegram_errors_keep_aiogram_types(monkeypatch, status, content, expected_exception):
    relay_session = TelegramRelaySession(RELAY_URL, RELAY_KEY)
    response = FakeResponse(status, json.dumps(content))
    http_session = FakeClientSession()
    http_session.post = lambda *args, **kwargs: FakeRequestContext(response)
    monkeypatch.setattr(relay_session, "create_session", AsyncMock(return_value=http_session))
    bot = Bot(token=BOT_TOKEN, session=relay_session)

    with pytest.raises(expected_exception) as exc_info:
        await bot(SendMessage(chat_id=42, text="hello"))

    assert exc_info.value.method.__api_method__ == "sendMessage"
    if expected_exception is TelegramRetryAfter:
        assert exc_info.value.retry_after == 7


@pytest.mark.parametrize("status", [400, 403, 404, 413])
async def test_worker_client_errors_are_not_telegram_client_errors(monkeypatch, status):
    relay_session = TelegramRelaySession(RELAY_URL, RELAY_KEY)
    response = FakeResponse(status, json.dumps({"ok": False, "error": "Relay rejected request"}))
    http_session = FakeClientSession()
    http_session.post = lambda *args, **kwargs: FakeRequestContext(response)
    monkeypatch.setattr(relay_session, "create_session", AsyncMock(return_value=http_session))
    bot = Bot(token=BOT_TOKEN, session=relay_session)

    with pytest.raises(TelegramAPIError) as exc_info:
        await bot(SendMessage(chat_id=42, text="hello"))

    assert type(exc_info.value) is TelegramAPIError
    assert "Relay rejected request" in str(exc_info.value)
    assert exc_info.value.method.__api_method__ == "sendMessage"


@pytest.mark.parametrize("status", [500, 502, 504])
async def test_worker_http_errors_keep_aiogram_exception(monkeypatch, status):
    relay_session = TelegramRelaySession(RELAY_URL, RELAY_KEY)
    response = FakeResponse(status, json.dumps({"ok": False, "error": "Relay unavailable"}))
    http_session = FakeClientSession()
    http_session.post = lambda *args, **kwargs: FakeRequestContext(response)
    monkeypatch.setattr(relay_session, "create_session", AsyncMock(return_value=http_session))
    bot = Bot(token=BOT_TOKEN, session=relay_session)

    with pytest.raises(TelegramServerError) as exc_info:
        await bot(GetUpdates(timeout=10))

    assert "Relay unavailable" in str(exc_info.value)
    assert exc_info.value.method.__api_method__ == "getUpdates"


async def test_post_disables_cross_origin_redirects(monkeypatch):
    bot, http_session = make_bot_and_http_session(monkeypatch, result=[])

    await bot(GetUpdates(timeout=10))

    assert len(http_session.requests) == 1
    assert http_session.requests[0]["allow_redirects"] is False


async def test_network_timeout_keeps_aiogram_exception(monkeypatch):
    bot, _ = make_bot_and_http_session(monkeypatch, error=TimeoutError())

    with pytest.raises(TelegramNetworkError, match="Request timeout error"):
        await bot(GetUpdates(timeout=10))


async def test_per_request_timeout_is_preserved(monkeypatch):
    bot, http_session = make_bot_and_http_session(monkeypatch, result=[])

    await bot(GetUpdates(timeout=10), request_timeout=7)

    assert http_session.requests[0]["timeout"] == 7


def test_session_inherits_aiogram_form_response_and_timeout_behavior():
    session = TelegramRelaySession(RELAY_URL + "/", RELAY_KEY, timeout=12)

    assert isinstance(session, AiohttpSession)
    assert TelegramRelaySession.build_form_data is AiohttpSession.build_form_data
    assert TelegramRelaySession.check_response is AiohttpSession.check_response
    assert session.timeout == 12
    assert session.api.base == f"{RELAY_URL}/{{method}}"

    file_url = session.api.file_url(BOT_TOKEN, "documents/file.txt")
    assert file_url == f"{RELAY_URL}/file/documents/file.txt"
    assert BOT_TOKEN not in file_url
    assert "api.telegram.org" not in file_url


class FakeStreamContent:
    def __init__(self, captured) -> None:
        self.captured = captured

    async def iter_chunked(self, chunk_size):
        self.captured["chunk_size"] = chunk_size
        yield b"content"


class FakeStreamResponse:
    def __init__(self, captured) -> None:
        self.content = FakeStreamContent(captured)


class FakeStreamContext:
    def __init__(self, captured) -> None:
        self.captured = captured

    async def __aenter__(self):
        return FakeStreamResponse(self.captured)

    async def __aexit__(self, *args):
        return None


class FakeStreamSession:
    def __init__(self) -> None:
        self.captured = {}

    def get(self, url, *, timeout, headers, raise_for_status, allow_redirects):
        self.captured.update(
            url=url,
            timeout=timeout,
            headers=headers,
            raise_for_status=raise_for_status,
            allow_redirects=allow_redirects,
        )
        return FakeStreamContext(self.captured)


async def test_streaming_request_uses_aiohttp_with_relay_key_and_options(monkeypatch):
    http_session = FakeStreamSession()
    session = TelegramRelaySession(RELAY_URL, RELAY_KEY)
    monkeypatch.setattr(session, "create_session", AsyncMock(return_value=http_session))
    url = "https://relay.example.test:443/file/document"

    chunks = [
        chunk
        async for chunk in session.stream_content(
            url,
            headers={"X-Custom": "value"},
            timeout=17,
            chunk_size=128,
            raise_for_status=False,
        )
    ]

    assert chunks == [b"content"]
    assert http_session.captured == {
        "url": url,
        "timeout": 17,
        "headers": {"X-Custom": "value", "X-Relay-Key": RELAY_KEY},
        "raise_for_status": False,
        "allow_redirects": False,
        "chunk_size": 128,
    }


@pytest.mark.parametrize(
    "url",
    [
        "https://files.example.test/document",
        "http://relay.example.test/document",
        "https://relay.example.test:444/document",
    ],
)
async def test_streaming_foreign_origin_does_not_receive_relay_key(monkeypatch, url):
    http_session = FakeStreamSession()
    session = TelegramRelaySession(RELAY_URL, RELAY_KEY)
    monkeypatch.setattr(session, "create_session", AsyncMock(return_value=http_session))
    original_headers = {"X-Custom": "value"}

    chunks = [chunk async for chunk in session.stream_content(url, headers=original_headers)]

    assert chunks == [b"content"]
    assert http_session.captured["headers"] == original_headers
    assert "X-Relay-Key" not in http_session.captured["headers"]
    assert http_session.captured["allow_redirects"] is False
    assert original_headers == {"X-Custom": "value"}


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Relay-Key": RELAY_KEY, "X-Custom": "value"},
        CIMultiDict({"x-rElAy-KeY": RELAY_KEY, "X-Custom": "value"}),
    ],
)
async def test_streaming_foreign_origin_strips_prepopulated_relay_key(monkeypatch, headers):
    http_session = FakeStreamSession()
    session = TelegramRelaySession(RELAY_URL, RELAY_KEY)
    monkeypatch.setattr(session, "create_session", AsyncMock(return_value=http_session))

    chunks = [
        chunk
        async for chunk in session.stream_content("https://files.example.test/document", headers=headers)
    ]

    assert chunks == [b"content"]
    assert http_session.captured["headers"] == {"X-Custom": "value"}
    assert headers.get("X-Relay-Key") == RELAY_KEY


def make_settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "telegram_bot_token": BOT_TOKEN,
        "bot_secret": "test-bot-secret",
        "cron_secret": "test-cron-secret",
        "uptime_secret": "test-uptime-secret",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize("relay_url,relay_key", [("", ""), (RELAY_URL, RELAY_KEY)])
def test_relay_settings_require_both_or_neither(relay_url, relay_key):
    settings = make_settings(telegram_relay_url=relay_url, telegram_relay_key=relay_key)

    assert settings.telegram_relay_url == relay_url
    assert settings.telegram_relay_key == relay_key


@pytest.mark.parametrize("relay_url,relay_key", [(RELAY_URL, ""), ("", RELAY_KEY)])
def test_incomplete_relay_settings_fail_fast(relay_url, relay_key):
    with pytest.raises(ValidationError, match="must be set together"):
        make_settings(telegram_relay_url=relay_url, telegram_relay_key=relay_key)


@pytest.mark.parametrize(
    "relay_url",
    [
        "http://relay.example.test",
        "relay.example.test",
        "https://relay.example.test/{token}",
        "https://user:password@relay.example.test",
        "https://relay.example.test/?mode=relay",
        "https://relay.example.test/#fragment",
        f"https://relay.example.test/{BOT_TOKEN}",
    ],
)
def test_relay_url_must_be_https_without_credentials_or_token(relay_url):
    with pytest.raises(ValidationError):
        make_settings(telegram_relay_url=relay_url, telegram_relay_key=RELAY_KEY)

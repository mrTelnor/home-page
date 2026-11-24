import inspect

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services import email as email_mod
from app.services import telegram as tg_mod

BOT_TOKEN = "test-bot-token"
RELAY_URL = "https://relay.example.test"
RELAY_KEY = "test-relay-key"


@pytest.fixture(autouse=True)
def direct_telegram_mode(monkeypatch):
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_url", "")
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_key", "")


def telegram_response(status_code=200, payload=None, content=None):
    request = httpx.Request("POST", RELAY_URL, headers={"X-Relay-Key": RELAY_KEY})
    if content is not None:
        return httpx.Response(status_code, content=content, request=request)
    return httpx.Response(
        status_code,
        json={"ok": True, "result": {"message_id": 1}} if payload is None else payload,
        request=request,
    )


def install_telegram_client(monkeypatch, response=None, error=None):
    captured = {"calls": []}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            captured["calls"].append({"url": url, "headers": headers, "json": json})
            if error is not None:
                raise error
            return response

    monkeypatch.setattr(tg_mod.httpx, "AsyncClient", FakeClient)
    return captured


def make_settings(**overrides):
    values = {
        "_env_file": None,
        "database_url": "postgresql+asyncpg://test/test",
        "jwt_secret": "test-jwt-secret",
        "invite_code": "test-invite",
        "cron_secret": "test-cron-secret",
        "telegram_bot_token": BOT_TOKEN,
        "telegram_bot_username": "test_bot",
        "bot_secret": "test-bot-secret",
    }
    values.update(overrides)
    return Settings(**values)


def test_public_telegram_signature_and_bot_token_requirement():
    signature = inspect.signature(tg_mod.send_telegram_message)

    assert list(signature.parameters) == ["tg_id", "text"]
    assert signature.return_annotation is bool
    assert Settings.model_fields["telegram_bot_token"].is_required()


async def test_send_telegram_direct_mode_when_relay_is_empty(monkeypatch):
    captured = install_telegram_client(monkeypatch, response=telegram_response())

    ok = await tg_mod.send_telegram_message(12345, "hello")

    assert ok is True
    assert captured["url"] == f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    assert captured["headers"] is None
    assert captured["json"] == {"chat_id": 12345, "text": "hello"}


async def test_send_telegram_uses_relay_without_bot_token(monkeypatch):
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_url", RELAY_URL)
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_key", RELAY_KEY)
    captured = install_telegram_client(monkeypatch, response=telegram_response())

    ok = await tg_mod.send_telegram_message(12345, "hello")

    assert ok is True
    assert captured["url"] == f"{RELAY_URL}/sendMessage"
    assert BOT_TOKEN not in captured["url"]
    assert "api.telegram.org" not in captured["url"]
    assert captured["headers"] == {"X-Relay-Key": RELAY_KEY}
    assert captured["json"] == {"chat_id": 12345, "text": "hello"}
    assert captured["timeout"] == 10
    assert len(captured["calls"]) == 1


async def test_send_telegram_rejects_telegram_error_with_http_200(monkeypatch, caplog):
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_url", RELAY_URL)
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_key", RELAY_KEY)
    captured = install_telegram_client(
        monkeypatch,
        response=telegram_response(payload={"ok": False, "error_code": 400, "description": "body-secret"}),
    )

    assert await tg_mod.send_telegram_message(1, "x") is False
    assert len(captured["calls"]) == 1
    assert captured["url"] == f"{RELAY_URL}/sendMessage"
    assert "body-secret" not in caplog.text
    assert RELAY_URL not in caplog.text
    assert RELAY_KEY not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize("payload", [{}, {"result": {"message_id": 1}}, {"ok": 1}, {"ok": "true"}, []])
async def test_send_telegram_requires_json_object_with_boolean_ok_true(monkeypatch, payload):
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_url", RELAY_URL)
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_key", RELAY_KEY)
    captured = install_telegram_client(monkeypatch, response=telegram_response(payload=payload))

    assert await tg_mod.send_telegram_message(1, "x") is False
    assert len(captured["calls"]) == 1


@pytest.mark.parametrize("content", [b'{"ok":', b"not-json", b""])
async def test_send_telegram_rejects_invalid_json_without_fallback(monkeypatch, caplog, content):
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_url", RELAY_URL)
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_key", RELAY_KEY)
    captured = install_telegram_client(monkeypatch, response=telegram_response(content=content))

    assert await tg_mod.send_telegram_message(1, "x") is False
    assert len(captured["calls"]) == 1
    assert captured["url"] == f"{RELAY_URL}/sendMessage"
    assert RELAY_URL not in caplog.text
    assert RELAY_KEY not in caplog.text
    assert BOT_TOKEN not in caplog.text
    assert "Traceback" not in caplog.text


async def test_send_telegram_rejects_http_error_without_direct_fallback(monkeypatch, caplog):
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_url", RELAY_URL)
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_key", RELAY_KEY)
    captured = install_telegram_client(
        monkeypatch,
        response=telegram_response(status_code=503, content=b'{"ok":false,"description":"body-secret"}'),
    )

    assert await tg_mod.send_telegram_message(1, "x") is False
    assert len(captured["calls"]) == 1
    assert captured["url"] == f"{RELAY_URL}/sendMessage"
    assert "body-secret" not in caplog.text
    assert RELAY_URL not in caplog.text
    assert RELAY_KEY not in caplog.text
    assert BOT_TOKEN not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError(f"network {RELAY_URL} {RELAY_KEY} {BOT_TOKEN}"),
        httpx.ReadTimeout(f"timeout {RELAY_URL} {RELAY_KEY} {BOT_TOKEN}"),
    ],
)
async def test_send_telegram_swallows_network_errors_and_timeouts(monkeypatch, caplog, error):
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_url", RELAY_URL)
    monkeypatch.setattr(tg_mod.settings, "telegram_relay_key", RELAY_KEY)
    captured = install_telegram_client(monkeypatch, error=error)

    assert await tg_mod.send_telegram_message(1, "x") is False
    assert len(captured["calls"]) == 1
    assert captured["url"] == f"{RELAY_URL}/sendMessage"
    assert RELAY_KEY not in caplog.text
    assert RELAY_URL not in caplog.text
    assert BOT_TOKEN not in caplog.text
    assert "network" not in caplog.text
    assert "timeout" not in caplog.text
    assert "Traceback" not in caplog.text


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
        "https://relay.example.test:not-a-port",
        "https://relay.example.test:99999",
    ],
)
def test_relay_url_must_be_https_without_credentials_or_token(relay_url):
    with pytest.raises(ValidationError):
        make_settings(telegram_relay_url=relay_url, telegram_relay_key=RELAY_KEY)


async def test_send_email_skips_without_key(monkeypatch):
    monkeypatch.setattr(email_mod.settings, "rusender_api_key", None)
    assert await email_mod.send_email("a@b.c", "subj", "<p>x</p>") is False


async def test_send_email_posts_to_rusender(monkeypatch):
    captured = {}
    monkeypatch.setattr(email_mod.settings, "rusender_api_key", "rs_ck_test")
    monkeypatch.setattr(email_mod.settings, "rusender_key_id", "5555")
    monkeypatch.setattr(email_mod.settings, "email_from", "Telnor <noreply@telnor.ru>")

    class FakeResponse:
        def raise_for_status(self): pass

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(email_mod.httpx, "AsyncClient", FakeClient)
    ok = await email_mod.send_email("a@b.c", "subj", "<p>x</p>")
    assert ok is True
    assert captured["url"] == "https://api.rusender.ru/api/v1/external-mails/send/5555"
    assert captured["headers"]["Authorization"] == "Bearer rs_ck_test"
    mail = captured["json"]["mail"]
    assert mail["to"] == {"email": "a@b.c"}
    assert mail["from"] == {"email": "noreply@telnor.ru", "name": "Telnor"}
    assert mail["subject"] == "subj"
    assert mail["html"] == "<p>x</p>"

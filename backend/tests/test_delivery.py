import httpx
import pytest

from app.services import email as email_mod
from app.services import telegram as tg_mod

async def test_send_telegram_calls_bot_api(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self): pass

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, *, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(tg_mod.httpx, "AsyncClient", FakeClient)
    ok = await tg_mod.send_telegram_message(12345, "hello")
    assert ok is True
    assert "/sendMessage" in captured["url"]
    assert captured["json"]["chat_id"] == 12345
    assert captured["json"]["text"] == "hello"


async def test_send_telegram_swallows_errors(monkeypatch):
    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): raise httpx.HTTPError("boom")

    monkeypatch.setattr(tg_mod.httpx, "AsyncClient", FakeClient)
    assert await tg_mod.send_telegram_message(1, "x") is False


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

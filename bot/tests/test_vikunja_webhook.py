"""Тесты /vikunja-webhook: подпись, назначение, комментарий, фильтрация получателей."""
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app import vikunja, webserver
from app.webserver import create_app

SECRET = "test-vikunja-secret"
USER_MAP = {"telnor": "telnor", "Руслана": "blakot"}
NOTIFIABLE = [
    {"tg_id": 111, "username": "telnor"},
    {"tg_id": 222, "username": "blakot"},
]


def _user(login: str, name: str = "") -> dict:
    return {"id": 1, "username": login, "name": name}


def _task(assignees: list[str], title: str = "Починить бэкап") -> dict:
    return {"id": 42, "title": title, "assignees": [_user(a) for a in assignees]}


def _signed(payload: dict, secret: str = SECRET) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, {"X-Vikunja-Signature": sig, "Content-Type": "application/json"}


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(vikunja.settings, "vikunja_webhook_secret", SECRET)
    monkeypatch.setattr(vikunja.settings, "vikunja_user_map", json.dumps(USER_MAP))
    monkeypatch.setattr(vikunja.settings, "vikunja_url", "https://tracker.example")
    monkeypatch.setattr(webserver.api, "get_tracker_notifiable_users", AsyncMock(return_value=NOTIFIABLE))
    bot = MagicMock()
    bot.send_message = AsyncMock()
    app = create_app(bot)
    async with TestClient(TestServer(app)) as c:
        c.bot = bot
        yield c


async def _post(client, payload: dict, secret: str = SECRET):
    body, headers = _signed(payload, secret)
    return await client.post("/vikunja-webhook", data=body, headers=headers)


def _sent(client) -> dict[int, str]:
    return {c.kwargs["chat_id"]: c.kwargs["text"] for c in client.bot.send_message.await_args_list}


async def test_rejects_missing_signature(client):
    resp = await client.post("/vikunja-webhook", json={"event_name": "task.assignee.created"})
    assert resp.status == 401
    client.bot.send_message.assert_not_awaited()


async def test_rejects_wrong_signature(client):
    resp = await _post(client, {"event_name": "task.assignee.created"}, secret="wrong")
    assert resp.status == 401


async def test_rejects_when_secret_not_configured(client, monkeypatch):
    monkeypatch.setattr(vikunja.settings, "vikunja_webhook_secret", "")
    body = b"{}"
    resp = await client.post("/vikunja-webhook", data=body, headers={"X-Vikunja-Signature": ""})
    assert resp.status == 401


async def test_invalid_json(client):
    body = b"not json"
    sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    resp = await client.post("/vikunja-webhook", data=body, headers={"X-Vikunja-Signature": sig})
    assert resp.status == 400


async def test_assignee_created_notifies_assignee(client):
    payload = {
        "event_name": "task.assignee.created",
        "data": {"task": _task(["Руслана"]), "assignee": _user("Руслана"), "doer": _user("telnor", "Никита")},
    }
    resp = await _post(client, payload)
    assert resp.status == 200
    assert (await resp.json())["sent"] == 1
    sent = _sent(client)
    assert list(sent) == [222]
    text = sent[222]
    assert "📋 Тебя назначили на задачу «Починить бэкап»" in text
    assert "от: Никита" in text
    assert "https://tracker.example/tasks/42" in text


async def test_assignee_created_self_assign_skipped(client):
    payload = {
        "event_name": "task.assignee.created",
        "data": {"task": _task(["telnor"]), "assignee": _user("telnor"), "doer": _user("telnor")},
    }
    resp = await _post(client, payload)
    assert resp.status == 200
    client.bot.send_message.assert_not_awaited()


async def test_comment_created_notifies_assignees_except_doer(client):
    payload = {
        "event_name": "task.comment.created",
        "data": {
            "task": _task(["telnor", "Руслана"]),
            "comment": {"comment": "<p>Готово, <b>проверь</b> &amp; закрой</p>"},
            "doer": _user("telnor", "Никита"),
        },
    }
    resp = await _post(client, payload)
    assert resp.status == 200
    sent = _sent(client)
    assert list(sent) == [222]
    text = sent[222]
    assert "💬 Никита прокомментировал «Починить бэкап»:" in text
    assert "Готово, проверь &amp; закрой" in text
    assert "<p>" not in text


async def test_comment_is_truncated(client):
    payload = {
        "event_name": "task.comment.created",
        "data": {"task": _task(["Руслана"]), "comment": {"comment": "а" * 500}, "doer": _user("telnor")},
    }
    await _post(client, payload)
    text = _sent(client)[222]
    assert "а" * 300 + "…" in text
    assert "а" * 301 not in text


async def test_title_is_html_escaped(client):
    payload = {
        "event_name": "task.assignee.created",
        "data": {"task": _task(["telnor"], title="<script>"), "assignee": _user("telnor"), "doer": _user("claude")},
    }
    await _post(client, payload)
    assert "«&lt;script&gt;»" in _sent(client)[111]


async def test_login_not_in_map_skipped(client):
    payload = {
        "event_name": "task.assignee.created",
        "data": {"task": _task(["claude"]), "assignee": _user("claude"), "doer": _user("telnor")},
    }
    resp = await _post(client, payload)
    assert resp.status == 200
    assert (await resp.json())["sent"] == 0
    client.bot.send_message.assert_not_awaited()


async def test_muted_user_skipped(client, monkeypatch):
    # трекер выключен (/notifications или /mute): backend не отдаёт пользователя
    monkeypatch.setattr(webserver.api, "get_tracker_notifiable_users", AsyncMock(return_value=NOTIFIABLE[:1]))
    payload = {
        "event_name": "task.assignee.created",
        "data": {"task": _task(["Руслана"]), "assignee": _user("Руслана"), "doer": _user("telnor")},
    }
    resp = await _post(client, payload)
    assert resp.status == 200
    client.bot.send_message.assert_not_awaited()


async def test_unknown_event_ignored(client):
    payload = {"event_name": "task.updated", "data": {"task": _task(["telnor"]), "doer": _user("claude")}}
    resp = await _post(client, payload)
    assert resp.status == 200
    assert (await resp.json())["sent"] == 0
    webserver.api.get_tracker_notifiable_users.assert_not_awaited()


async def test_telegram_error_does_not_fail_webhook(client):
    from aiogram.exceptions import TelegramForbiddenError

    client.bot.send_message.side_effect = TelegramForbiddenError(method=MagicMock(), message="blocked")
    payload = {
        "event_name": "task.assignee.created",
        "data": {"task": _task(["telnor"]), "assignee": _user("telnor"), "doer": _user("claude")},
    }
    resp = await _post(client, payload)
    assert resp.status == 200
    assert (await resp.json())["sent"] == 0


async def test_log_distinguishes_not_in_map_and_disabled(client, monkeypatch, caplog):
    monkeypatch.setattr(webserver.api, "get_tracker_notifiable_users", AsyncMock(return_value=[]))
    payload = {
        "event_name": "task.comment.created",
        "data": {"task": _task(["telnor", "claude"]), "comment": {"comment": "x"}, "doer": _user("Руслана")},
    }
    with caplog.at_level("INFO", logger="app.webserver"):
        await _post(client, payload)
    assert "логина claude нет в VIKUNJA_USER_MAP" in caplog.text
    assert "telnor (сайт: telnor) — трекер выключен или Telegram не привязан" in caplog.text


def test_broken_user_map_is_empty(monkeypatch):
    monkeypatch.setattr(vikunja.settings, "vikunja_user_map", "{broken")
    assert vikunja.user_map() == {}

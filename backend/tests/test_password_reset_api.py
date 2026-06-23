import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

import app.services.password_reset as pr
from app.db.models.password_reset import PasswordResetToken
from tests.conftest import TestSessionMaker, _create_user_standalone


@pytest.fixture(autouse=True)
def _stub_delivery(monkeypatch):
    sent = {"tg": [], "email": []}

    async def fake_tg(tg_id, text):
        sent["tg"].append((tg_id, text))
        return True

    async def fake_email(to, subject, html):
        sent["email"].append((to, subject, html))
        return True

    monkeypatch.setattr(pr, "send_telegram_message", fake_tg)
    monkeypatch.setattr(pr, "send_email", fake_email)
    return sent


async def test_request_email_path_always_sent(client):
    await _create_user_standalone("emailer", email="e@x.com")
    resp = await client.post("/api/auth/password-reset/request", json={"identifier": "e@x.com"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


async def test_request_unknown_email_still_sent(client):
    resp = await client.post("/api/auth/password-reset/request", json={"identifier": "nobody@x.com"})
    assert resp.json()["status"] == "sent"


async def test_request_login_no_channels(client):
    await _create_user_standalone("lonely")  # ни tg, ни email
    resp = await client.post("/api/auth/password-reset/request", json={"identifier": "lonely"})
    assert resp.json()["status"] == "no_channels"


async def test_request_login_two_channels_choose(client, _stub_delivery):
    await _create_user_standalone("both", tg_id=999, email="b@x.com")
    resp = await client.post("/api/auth/password-reset/request", json={"identifier": "both"})
    body = resp.json()
    assert body["status"] == "choose"
    assert set(body["channels"]) == {"telegram", "email"}
    assert _stub_delivery["tg"] == []
    assert _stub_delivery["email"] == []


async def test_request_login_one_channel_sent(client, _stub_delivery):
    await _create_user_standalone("tgonly", tg_id=555)
    resp = await client.post("/api/auth/password-reset/request", json={"identifier": "tgonly"})
    assert resp.json()["status"] == "sent"
    assert _stub_delivery["tg"]


async def test_request_with_channel_sends(client, _stub_delivery):
    await _create_user_standalone("both2", tg_id=111, email="b2@x.com")
    resp = await client.post(
        "/api/auth/password-reset/request",
        json={"identifier": "both2", "channel": "email"},
    )
    assert resp.json()["status"] == "sent"
    assert _stub_delivery["email"]


async def test_confirm_resets_password(client):
    user = await _create_user_standalone("confirmer", email="c@x.com")
    async with TestSessionMaker() as session:
        u = await session.get(type(user), user.id)
        raw, _ = await pr.create_reset_token(session, u, "email")
    resp = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": raw, "new_password": "brandnew123"},
    )
    assert resp.status_code == 200
    login = await client.post("/api/auth/login", json={"username": "confirmer", "password": "brandnew123"})
    assert login.status_code == 200


async def test_confirm_rejects_bad_token(client):
    resp = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "nope", "new_password": "brandnew123"},
    )
    assert resp.status_code == 400


async def test_confirm_token_single_use(client):
    user = await _create_user_standalone("single", email="s@x.com")
    async with TestSessionMaker() as session:
        u = await session.get(type(user), user.id)
        raw, _ = await pr.create_reset_token(session, u, "email")
    first = await client.post("/api/auth/password-reset/confirm", json={"token": raw, "new_password": "brandnew123"})
    assert first.status_code == 200
    second = await client.post("/api/auth/password-reset/confirm", json={"token": raw, "new_password": "another123"})
    assert second.status_code == 400


async def test_validate_endpoint(client):
    user = await _create_user_standalone("validator", email="v@x.com")
    async with TestSessionMaker() as session:
        u = await session.get(type(user), user.id)
        raw, _ = await pr.create_reset_token(session, u, "email")
    ok = await client.get(f"/api/auth/password-reset/validate?token={raw}")
    assert ok.json()["valid"] is True
    bad = await client.get("/api/auth/password-reset/validate?token=nope")
    assert bad.json()["valid"] is False


async def test_confirm_rejects_already_used_token(client):
    user = await _create_user_standalone("usedtok", email="u@x.com")
    async with TestSessionMaker() as session:
        u = await session.get(type(user), user.id)
        raw, _ = await pr.create_reset_token(session, u, "email")
    # mark the token used directly in DB before attempting confirm
    async with TestSessionMaker() as session:
        row = (await session.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))).scalar_one()
        row.used_at = datetime.now(UTC)
        await session.commit()
    resp = await client.post("/api/auth/password-reset/confirm", json={"token": raw, "new_password": "whatever12345"})
    assert resp.status_code == 400

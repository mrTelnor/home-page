import hashlib
import hmac
import time

from httpx import AsyncClient

from app.db.models.user import User
from app.services.telegram import verify_telegram_auth

BOT_TOKEN = "test-bot-token"
BOT_SECRET = "test-bot-secret"


def _make_telegram_payload(tg_id: int, bot_token: str = BOT_TOKEN) -> dict:
    """Создать корректно подписанный payload от имитации Telegram."""
    payload = {
        "id": tg_id,
        "first_name": "Иван",
        "auth_date": int(time.time()),
    }
    check_string = "\n".join(f"{k}={payload[k]}" for k in sorted(payload.keys()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    payload["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return payload


# ---------- HMAC verify (unit) ----------

def test_verify_telegram_auth_valid():
    payload = _make_telegram_payload(12345)
    assert verify_telegram_auth(payload, BOT_TOKEN) is True


def test_verify_telegram_auth_invalid_hash():
    payload = _make_telegram_payload(12345)
    payload["hash"] = "0" * 64
    assert verify_telegram_auth(payload, BOT_TOKEN) is False


def test_verify_telegram_auth_expired():
    payload = {
        "id": 12345,
        "first_name": "Иван",
        "auth_date": int(time.time()) - 7200,  # 2 часа назад
    }
    check_string = "\n".join(f"{k}={payload[k]}" for k in sorted(payload.keys()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    payload["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    assert verify_telegram_auth(payload, BOT_TOKEN) is False


def test_verify_telegram_auth_wrong_token():
    payload = _make_telegram_payload(12345, bot_token="wrong-token")
    assert verify_telegram_auth(payload, BOT_TOKEN) is False


# ---------- POST /api/auth/telegram-verify ----------

async def test_telegram_verify_success(authed_client: AsyncClient):
    payload = _make_telegram_payload(55555)
    response = await authed_client.post("/api/auth/telegram-verify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["tg_id"] == 55555


async def test_telegram_verify_invalid_signature(authed_client: AsyncClient):
    payload = _make_telegram_payload(55555)
    payload["hash"] = "0" * 64
    response = await authed_client.post("/api/auth/telegram-verify", json=payload)
    assert response.status_code == 401


async def test_telegram_verify_already_linked(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    # Admin привязывает tg_id=777
    payload = _make_telegram_payload(777)
    response = await admin_client.post("/api/auth/telegram-verify", json=payload)
    assert response.status_code == 200

    # authed_client (testuser) пытается привязать тот же tg_id
    payload2 = _make_telegram_payload(777)
    response2 = await authed_client.post("/api/auth/telegram-verify", json=payload2)
    assert response2.status_code == 409


# ---------- POST /api/auth/telegram-unlink ----------

async def test_telegram_unlink(authed_client: AsyncClient):
    # Сначала привязка
    payload = _make_telegram_payload(888)
    await authed_client.post("/api/auth/telegram-verify", json=payload)

    response = await authed_client.post("/api/auth/telegram-unlink")
    assert response.status_code == 200
    data = response.json()
    assert data["tg_id"] is None


# ---------- POST /api/auth/telegram-login (для бота) ----------

async def test_telegram_login_success(authed_client: AsyncClient):
    payload = _make_telegram_payload(999)
    await authed_client.post("/api/auth/telegram-verify", json=payload)

    response = await authed_client.post(
        "/api/auth/telegram-login",
        headers={"X-Bot-Secret": BOT_SECRET},
        json={"tg_id": 999},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


async def test_telegram_login_wrong_secret(client: AsyncClient):
    response = await client.post(
        "/api/auth/telegram-login",
        headers={"X-Bot-Secret": "wrong"},
        json={"tg_id": 999},
    )
    assert response.status_code == 403


async def test_telegram_login_unknown_tg_id(client: AsyncClient):
    response = await client.post(
        "/api/auth/telegram-login",
        headers={"X-Bot-Secret": BOT_SECRET},
        json={"tg_id": 12345678},
    )
    assert response.status_code == 404

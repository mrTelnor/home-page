import hashlib
import hmac
import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Дедуп использованных подписей Login Widget (защита от replay в пределах окна).
# In-memory: один uvicorn-воркер; после рестарта очищается, что в пределах
# минутного окна валидности несущественно.
_used_auth_hashes: dict[str, float] = {}


def mark_telegram_auth_used(auth_hash: str, ttl_seconds: int, now: float | None = None) -> bool:
    """Отметить подпись использованной. False, если она уже применялась (replay)."""
    ts = now if now is not None else time.time()
    # прунинг протухших
    for key in [k for k, exp in _used_auth_hashes.items() if exp <= ts]:
        del _used_auth_hashes[key]
    if auth_hash in _used_auth_hashes:
        return False
    _used_auth_hashes[auth_hash] = ts + ttl_seconds
    return True


def verify_telegram_auth(data: dict, bot_token: str, max_age_seconds: int = 3600) -> bool:
    """
    Проверка HMAC-подписи от Telegram Login Widget.
    Алгоритм: https://core.telegram.org/widgets/login#checking-authorization
    """
    received_hash = data.get("hash")
    if not received_hash:
        return False

    auth_date = data.get("auth_date")
    if not auth_date or time.time() - int(auth_date) > max_age_seconds:
        return False

    check_fields = {k: v for k, v in data.items() if k != "hash" and v is not None}
    data_check_string = "\n".join(f"{k}={check_fields[k]}" for k in sorted(check_fields.keys()))

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(computed_hash, received_hash)


async def send_telegram_message(tg_id: int, text: str) -> bool:
    if settings.telegram_relay_url:
        url = f"{settings.telegram_relay_url.rstrip('/')}/sendMessage"
        headers = {"X-Relay-Key": settings.telegram_relay_key}
    else:
        # Временный путь отката до отдельного cleanup после приёмки Worker.
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        headers = None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=headers, json={"chat_id": tg_id, "text": text})
            resp.raise_for_status()
            result = resp.json()
        if not isinstance(result, dict) or result.get("ok") is not True:
            logger.error("Telegram sendMessage returned an unsuccessful response for tg_id=%s", tg_id)
            return False
        return True
    except (httpx.HTTPError, ValueError) as exc:
        # Не выводим exc/traceback: в сообщении HTTPX может быть URL с токеном.
        logger.error("Telegram sendMessage failed for tg_id=%s error=%s", tg_id, type(exc).__name__)
        return False

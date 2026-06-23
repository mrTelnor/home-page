import hashlib
import hmac
import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


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
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"chat_id": tg_id, "text": text})
            resp.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception("Telegram sendMessage failed for tg_id=%s", tg_id)
        return False

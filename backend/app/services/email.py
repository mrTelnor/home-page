import logging
from email.utils import parseaddr

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RUSENDER_BASE_URL = "https://api.rusender.ru/api/v1/external-mails/send"


async def send_email(to: str, subject: str, html: str) -> bool:
    if not settings.rusender_api_key or not settings.rusender_key_id:
        logger.warning("RUSENDER_API_KEY/RUSENDER_KEY_ID не заданы; письмо для %s не отправлено", to)
        return False
    from_name, from_address = parseaddr(settings.email_from)
    from_obj: dict[str, str] = {"email": from_address}
    if from_name:
        from_obj["name"] = from_name
    payload = {
        "mail": {
            "to": {"email": to},
            "from": from_obj,
            "subject": subject,
            "html": html,
        }
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{RUSENDER_BASE_URL}/{settings.rusender_key_id}",
                headers={"Authorization": f"Bearer {settings.rusender_api_key}"},
                json=payload,
            )
            resp.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception("RuSender send failed to %s", to)
        return False

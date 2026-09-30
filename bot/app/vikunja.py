"""Webhook-события трекера Vikunja → тексты уведомлений в Telegram.

Vikunja подписывает тело запроса: X-Vikunja-Signature = hex(HMAC-SHA256(body, secret)).
Payload: {"event_name": ..., "time": ..., "data": {...}}; в data задача (task)
приходит перечитанной целиком — вместе с assignees.
"""
import hashlib
import hmac
import html
import json
import logging
import re

from aiogram.utils.text_decorations import html_decoration

from app.config import settings

logger = logging.getLogger(__name__)

EVENT_ASSIGNEE_CREATED = "task.assignee.created"
EVENT_COMMENT_CREATED = "task.comment.created"

COMMENT_PREVIEW_LIMIT = 300

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def signature_ok(body: bytes, provided: str | None, secret: str) -> bool:
    """Проверка подписи в постоянном времени. Пустой секрет — отказ всем."""
    if not secret or not provided:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided.strip().lower(), expected)


def user_map() -> dict[str, str]:
    """VIKUNJA_USER_MAP: {"логин Vikunja": "логин telnor.ru"}. Битый JSON — пустой словарь."""
    try:
        data = json.loads(settings.vikunja_user_map or "{}")
    except ValueError:
        logger.error("VIKUNJA_USER_MAP: невалидный JSON, уведомления трекера отключены")
        return {}
    if not isinstance(data, dict):
        logger.error("VIKUNJA_USER_MAP: ожидается объект, уведомления трекера отключены")
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _plain_text(value: str, limit: int = COMMENT_PREVIEW_LIMIT) -> str:
    """Комментарии Vikunja хранятся в HTML — в сообщение идёт текст без разметки."""
    text = _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value or ""))).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def _username(user: dict | None) -> str | None:
    return (user or {}).get("username") or None


def _display_name(user: dict | None) -> str:
    user = user or {}
    return user.get("name") or user.get("username") or "кто-то"


def build_notifications(payload: dict) -> list[tuple[str, str]]:
    """Список (логин Vikunja получателя, HTML-текст). Автору действия не шлём."""
    event = payload.get("event_name")
    data = payload.get("data") or {}
    task = data.get("task") or {}
    doer = data.get("doer")
    doer_login = _username(doer)

    title = html_decoration.quote(task.get("title") or "без названия")
    link = f"{settings.vikunja_url.rstrip('/')}/tasks/{task.get('id')}"
    doer_name = html_decoration.quote(_display_name(doer))

    if event == EVENT_ASSIGNEE_CREATED:
        assignee = _username(data.get("assignee"))
        if not assignee or assignee == doer_login:
            return []
        text = f"📋 Тебя назначили на задачу «{title}»\nот: {doer_name}\n{link}"
        return [(assignee, text)]

    if event == EVENT_COMMENT_CREATED:
        comment = html_decoration.quote(_plain_text((data.get("comment") or {}).get("comment", "")))
        text = f"💬 {doer_name} прокомментировал «{title}»:\n{comment}\n{link}"
        recipients = []
        for assignee in task.get("assignees") or []:
            login = _username(assignee)
            if login and login != doer_login and login not in recipients:
                recipients.append(login)
        return [(login, text) for login in recipients]

    return []

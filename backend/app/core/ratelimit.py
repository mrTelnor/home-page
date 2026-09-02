"""Rate limiting для публичных auth-эндпоинтов (slowapi, in-memory).

Backend работает одним uvicorn-воркером за Traefik, поэтому:
- хранилище счётчиков — in-memory (общего состояния между воркерами не нужно);
- реальный IP берём из X-Real-Ip (его выставляет Traefik; клиент не может
  подделать — Traefik перезаписывает заголовок). Фолбэк — последний хоп
  X-Forwarded-For (добавляется Traefik) и адрес соединения.
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def client_ip(request: Request) -> str:
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip, enabled=settings.rate_limit_enabled)

# Лимиты вынесены сюда, чтобы правились в одном месте
LOGIN_LIMIT = "10/minute"
REGISTER_LIMIT = "5/minute"
PASSWORD_RESET_LIMIT = "5/minute"

import asyncio
import ipaddress
import logging
import os
import secrets
import socket
import uuid
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3
_EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


async def _ensure_public_host(url: str) -> None:
    """Отклонить URL, чей хост резолвится в непубличный адрес (SSRF-защита).

    backend сидит в сети `internal` рядом с postgres/bot и в `web`, поэтому без
    проверки авторизованный пользователь мог бы направить запрос на
    http://postgres:5432, http://bot:8080, http://169.254.169.254 и т.п.
    Проверяются ВСЕ адреса из резолва (и IPv4, и IPv6); вызывается на каждом
    редирект-хопе.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported url scheme: {parsed.scheme}")
    host = parsed.hostname
    if not host:
        raise ValueError("missing host in url")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.run_in_executor(
            None, lambda: socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        )
    except socket.gaierror as exc:
        raise ValueError(f"cannot resolve host: {host}") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError(f"host resolves to non-public address: {ip}")


async def download_recipe_image(url: str, recipe_id: uuid.UUID) -> str:
    """Скачать изображение по url, сохранить в recipe_images_dir, вернуть путь раздачи.

    Бросает ValueError при неподходящей схеме/хосте (SSRF)/типе/размере.
    Редиректы обрабатываются вручную с проверкой хоста на каждом хопе; размер
    режется потоково, чтобы бесконечный ответ не съел память.
    """
    current = url
    data: bytes | None = None
    ext: str | None = None

    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await _ensure_public_host(current)
            async with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise ValueError("redirect without location")
                    current = str(resp.url.join(location))
                    continue

                resp.raise_for_status()

                content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                ext = _EXT_BY_TYPE.get(content_type)
                if ext is None:
                    raise ValueError(f"unsupported content-type: {content_type!r}")

                declared = resp.headers.get("content-length")
                if declared and int(declared) > MAX_BYTES:
                    raise ValueError("image too large")

                buf = bytearray()
                async for chunk in resp.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > MAX_BYTES:
                        raise ValueError("image too large")
                data = bytes(buf)
                break
        else:
            raise ValueError("too many redirects")

    os.makedirs(settings.recipe_images_dir, exist_ok=True)
    # Случайный суффикс: имя уникально на каждое скачивание, иначе замена фото
    # с тем же расширением удаляет только что записанный файл, а браузер
    # кэширует старую картинку по неизменному URL.
    filename = f"{recipe_id}-{secrets.token_hex(4)}.{ext}"
    with open(os.path.join(settings.recipe_images_dir, filename), "wb") as f:
        f.write(data)
    return f"/api/recipe-images/{filename}"


def delete_recipe_image(image_url: str | None) -> None:
    """Удалить файл фото по пути раздачи (если есть). Тихо игнорирует отсутствие."""
    if not image_url:
        return
    filename = image_url.rsplit("/", 1)[-1]
    path = os.path.join(settings.recipe_images_dir, filename)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass

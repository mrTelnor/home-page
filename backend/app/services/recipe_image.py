import logging
import os
import uuid
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024
_EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


async def download_recipe_image(url: str, recipe_id: uuid.UUID) -> str:
    """Скачать изображение по url, сохранить в recipe_images_dir, вернуть путь раздачи.

    Бросает ValueError при неподходящей схеме/типе/размере.
    """
    scheme = urlparse(url).scheme
    if scheme not in ("http", "https"):
        raise ValueError(f"unsupported url scheme: {scheme}")

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        resp = await client.get(url)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    ext = _EXT_BY_TYPE.get(content_type)
    if ext is None:
        raise ValueError(f"unsupported content-type: {content_type!r}")

    data = resp.content
    if len(data) > MAX_BYTES:
        raise ValueError("image too large")

    os.makedirs(settings.recipe_images_dir, exist_ok=True)
    filename = f"{recipe_id}.{ext}"
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

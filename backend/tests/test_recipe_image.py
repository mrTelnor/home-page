import uuid

import httpx
import pytest

from app.services import recipe_image
from app.services.recipe_image import download_recipe_image


def _mock_transport(monkeypatch, *, status=200, content=b"\xff\xd8\xff\xe0jpegbytes", content_type="image/jpeg"):
    async def fake_get(self, url, **kwargs):
        request = httpx.Request("GET", url)
        return httpx.Response(status, content=content, headers={"content-type": content_type}, request=request)
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)


async def test_download_saves_jpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    _mock_transport(monkeypatch)
    rid = uuid.uuid4()
    path = await download_recipe_image("https://example.com/a.jpg", rid)
    assert path == f"/api/recipe-images/{rid}.jpg"
    assert (tmp_path / f"{rid}.jpg").read_bytes().startswith(b"\xff\xd8")


async def test_download_rejects_non_http(monkeypatch, tmp_path):
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    with pytest.raises(ValueError, match="scheme"):
        await download_recipe_image("ftp://example.com/a.jpg", uuid.uuid4())


async def test_download_rejects_non_image(monkeypatch, tmp_path):
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    _mock_transport(monkeypatch, content_type="text/html")
    with pytest.raises(ValueError, match="content-type"):
        await download_recipe_image("https://example.com/a", uuid.uuid4())


async def test_download_rejects_too_large(monkeypatch, tmp_path):
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    _mock_transport(monkeypatch, content=b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="too large"):
        await download_recipe_image("https://example.com/a.jpg", uuid.uuid4())


async def test_download_maps_png_extension(monkeypatch, tmp_path):
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    _mock_transport(monkeypatch, content_type="image/png", content=b"\x89PNGdata")
    rid = uuid.uuid4()
    path = await download_recipe_image("https://example.com/a.png", rid)
    assert path.endswith(f"{rid}.png")


def test_delete_recipe_image_removes_file(monkeypatch, tmp_path):
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    f = tmp_path / "abc.jpg"
    f.write_bytes(b"x")
    recipe_image.delete_recipe_image("/api/recipe-images/abc.jpg")
    assert not f.exists()
    # повторный вызов и None — без ошибок
    recipe_image.delete_recipe_image("/api/recipe-images/abc.jpg")
    recipe_image.delete_recipe_image(None)

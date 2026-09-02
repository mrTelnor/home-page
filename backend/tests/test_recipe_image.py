import uuid

import httpx
import pytest

from app.services import recipe_image
from app.services.recipe_image import download_recipe_image


class _FakeStream:
    """Мок httpx-стрима: async-контекст-менеджер, отдающий готовый Response."""

    def __init__(self, status, content, headers, redirect_to=None):
        hdrs = dict(headers)
        if redirect_to is not None:
            hdrs["location"] = redirect_to
        self._resp = httpx.Response(
            status, content=content, headers=hdrs, request=httpx.Request("GET", "http://x/")
        )

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *exc):
        return False


def _mock_transport(monkeypatch, *, status=200, content=b"\xff\xd8\xff\xe0jpegbytes", content_type="image/jpeg"):
    """Мокает потоковую загрузку и отключает реальную DNS-проверку хоста."""
    monkeypatch.setattr(recipe_image, "_ensure_public_host", _async_noop)

    def fake_stream(self, method, url, **kwargs):
        return _FakeStream(status, content, {"content-type": content_type})

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)


async def _async_noop(*args, **kwargs):
    return None


async def test_download_saves_jpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    _mock_transport(monkeypatch)
    rid = uuid.uuid4()
    path = await download_recipe_image("https://example.com/a.jpg", rid)
    assert path.startswith(f"/api/recipe-images/{rid}-")
    assert path.endswith(".jpg")
    filename = path.rsplit("/", 1)[-1]
    assert (tmp_path / filename).read_bytes().startswith(b"\xff\xd8")


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
    assert str(rid) in path
    assert path.endswith(".png")


async def test_download_unique_filename_per_call(monkeypatch, tmp_path):
    """Каждое скачивание даёт уникальное имя файла — иначе при замене фото
    удаление старого url стирает только что записанный файл (та же {id}.{ext})."""
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    _mock_transport(monkeypatch)
    rid = uuid.uuid4()
    first = await download_recipe_image("https://example.com/a.jpg", rid)
    second = await download_recipe_image("https://example.com/b.jpg", rid)
    assert first != second


# ---------- SSRF-защита ----------


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/x.jpg",
    "http://localhost/x.jpg",
    "http://10.0.0.5/x.jpg",
    "http://192.168.1.10/x.jpg",
    "http://169.254.169.254/latest/meta-data",  # cloud metadata
    "http://[::1]/x.jpg",
])
async def test_download_rejects_private_and_loopback(monkeypatch, tmp_path, url):
    """URL, резолвящийся в приватный/loopback/link-local адрес, отвергается
    ДО запроса (SSRF: backend сидит в internal-сети рядом с postgres/bot)."""
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))

    def boom_stream(self, method, u, **kwargs):
        raise AssertionError("HTTP-запрос не должен выполняться для приватного адреса")

    monkeypatch.setattr(httpx.AsyncClient, "stream", boom_stream)
    with pytest.raises(ValueError, match="address|resolve|host"):
        await download_recipe_image(url, uuid.uuid4())


async def test_ensure_public_host_allows_public(monkeypatch):
    """Публичный адрес проходит проверку."""
    import socket

    def fake_getaddrinfo(host, port, *a, **kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(recipe_image.socket, "getaddrinfo", fake_getaddrinfo)
    # не бросает
    await recipe_image._ensure_public_host("https://example.com/a.jpg")


async def test_download_validates_each_redirect_hop(monkeypatch, tmp_path):
    """Хост проверяется на КАЖДОМ редирект-хопе, а не только на исходном URL."""
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    checked_hosts = []

    async def spy_check(url):
        from urllib.parse import urlparse
        host = urlparse(url).hostname
        checked_hosts.append(host)
        if host == "169.254.169.254":
            raise ValueError("host resolves to non-public address")

    monkeypatch.setattr(recipe_image, "_ensure_public_host", spy_check)

    def fake_stream(self, method, url, **kwargs):
        return _FakeStream(302, b"", {"content-type": "text/html"},
                           redirect_to="http://169.254.169.254/meta")

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    with pytest.raises(ValueError, match="non-public"):
        await download_recipe_image("https://example.com/pic.jpg", uuid.uuid4())
    assert "169.254.169.254" in checked_hosts, "редирект-хоп не был проверен"


async def test_download_rejects_oversized_stream_without_content_length(monkeypatch, tmp_path):
    """Размер режется по ходу чтения, даже если сервер не прислал Content-Length
    (иначе бесконечный поток съест память)."""
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    _mock_transport(monkeypatch, content=b"x" * (5 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="too large"):
        await download_recipe_image("https://example.com/a.jpg", uuid.uuid4())


def test_delete_recipe_image_removes_file(monkeypatch, tmp_path):
    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    f = tmp_path / "abc.jpg"
    f.write_bytes(b"x")
    recipe_image.delete_recipe_image("/api/recipe-images/abc.jpg")
    assert not f.exists()
    # повторный вызов и None — без ошибок
    recipe_image.delete_recipe_image("/api/recipe-images/abc.jpg")
    recipe_image.delete_recipe_image(None)

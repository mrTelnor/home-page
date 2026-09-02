from httpx import AsyncClient

from app.db.models.user import User


async def _async_return(value):
    return value


def _sample_recipe_payload(title: str = "Борщ") -> dict:
    return {
        "title": title,
        "description": "Классический борщ",
        "servings": 4,
        "ingredients": [
            {"name": "Свёкла", "amount": "2", "unit": "шт"},
            {"name": "Соль", "amount": "по вкусу", "unit": None},
        ],
    }


# ---------- CREATE ----------

async def test_create_recipe(authed_client: AsyncClient):
    response = await authed_client.post("/api/recipes", json=_sample_recipe_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Борщ"
    assert data["servings"] == 4
    assert len(data["ingredients"]) == 2


async def test_create_recipe_requires_auth(client: AsyncClient):
    response = await client.post("/api/recipes", json=_sample_recipe_payload())
    assert response.status_code == 401


# ---------- LIST ----------

async def test_list_recipes(authed_client: AsyncClient):
    r1 = await authed_client.post("/api/recipes", json=_sample_recipe_payload("Первый"))
    assert r1.status_code == 201, r1.text
    r2 = await authed_client.post("/api/recipes", json=_sample_recipe_payload("Второй"))
    assert r2.status_code == 201, r2.text

    response = await authed_client.get("/api/recipes")
    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------- GET ONE ----------

async def test_get_recipe(authed_client: AsyncClient):
    created = await authed_client.post("/api/recipes", json=_sample_recipe_payload())
    recipe_id = created.json()["id"]

    response = await authed_client.get(f"/api/recipes/{recipe_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Борщ"


async def test_get_recipe_not_found(authed_client: AsyncClient):
    response = await authed_client.get("/api/recipes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ---------- UPDATE ----------

async def test_update_own_recipe(authed_client: AsyncClient):
    created = await authed_client.post("/api/recipes", json=_sample_recipe_payload())
    recipe_id = created.json()["id"]

    response = await authed_client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Обновлённый борщ"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Обновлённый борщ"


async def test_update_foreign_recipe_forbidden(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    # admin создаёт рецепт
    created = await admin_client.post("/api/recipes", json=_sample_recipe_payload())
    recipe_id = created.json()["id"]

    # обычный user пытается обновить
    response = await authed_client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Хак"},
    )
    assert response.status_code == 403


async def test_admin_can_update_any_recipe(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    created = await authed_client.post("/api/recipes", json=_sample_recipe_payload())
    recipe_id = created.json()["id"]

    response = await admin_client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Admin edit"},
    )
    assert response.status_code == 200


# ---------- DELETE ----------

async def test_delete_own_recipe(authed_client: AsyncClient):
    created = await authed_client.post("/api/recipes", json=_sample_recipe_payload())
    recipe_id = created.json()["id"]

    response = await authed_client.delete(f"/api/recipes/{recipe_id}")
    assert response.status_code == 204


async def test_delete_foreign_recipe_forbidden(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    created = await admin_client.post("/api/recipes", json=_sample_recipe_payload())
    recipe_id = created.json()["id"]

    response = await authed_client.delete(f"/api/recipes/{recipe_id}")
    assert response.status_code == 403


async def test_update_recipe_not_found(authed_client: AsyncClient):
    response = await authed_client.put(
        "/api/recipes/00000000-0000-0000-0000-000000000000",
        json={"title": "Нет такого"},
    )
    assert response.status_code == 404


async def test_delete_recipe_not_found(authed_client: AsyncClient):
    response = await authed_client.delete(
        "/api/recipes/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


async def test_delete_recipe_in_active_voting(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    """Рецепт в активном голосовании удаляется soft-delete (204): пропадает из
    книги, но сохраняется в меню с настоящим названием."""
    created = await admin_client.post("/api/recipes", json=_sample_recipe_payload())
    recipe_id = created.json()["id"]

    # Создать ещё рецептов чтобы было минимум 3
    await admin_client.post("/api/recipes", json=_sample_recipe_payload("Суп"))
    await admin_client.post("/api/recipes", json=_sample_recipe_payload("Каша"))

    # Создать меню и финализировать — рецепт попадёт в активное голосование
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()
    await admin_client.post("/api/menus/finalize", json={})

    response = await admin_client.delete(f"/api/recipes/{recipe_id}")
    assert response.status_code == 204

    # Пропал из книги, но остался в меню с названием
    listed = (await admin_client.get("/api/recipes")).json()
    assert recipe_id not in {x["id"] for x in listed}
    menu_after = (await admin_client.get(f"/api/menus/{menu['id']}")).json()
    mr = next(x for x in menu_after["recipes"] if x["recipe_id"] == recipe_id)
    assert mr["title"] == created.json()["title"]


async def test_admin_can_delete_any_recipe(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    created = await authed_client.post("/api/recipes", json=_sample_recipe_payload())
    recipe_id = created.json()["id"]

    response = await admin_client.delete(f"/api/recipes/{recipe_id}")
    assert response.status_code == 204


# ---------- SEARCH ----------

async def test_search_recipes(authed_client: AsyncClient):
    await authed_client.post("/api/recipes", json=_sample_recipe_payload("Макароны по-флотски"))
    await authed_client.post("/api/recipes", json=_sample_recipe_payload("Макароны с сосисками"))
    await authed_client.post("/api/recipes", json=_sample_recipe_payload("Борщ"))

    response = await authed_client.get("/api/recipes/search?q=макароны")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    titles = {r["title"] for r in data}
    assert "Макароны по-флотски" in titles
    assert "Макароны с сосисками" in titles


async def test_search_recipes_no_results(authed_client: AsyncClient):
    response = await authed_client.get("/api/recipes/search?q=несуществующий")
    assert response.status_code == 200
    assert len(response.json()) == 0


async def test_search_recipes_public(client: AsyncClient):
    """Guest access: search is public, returns empty list without auth."""
    response = await client.get("/api/recipes/search?q=test")
    assert response.status_code == 200
    assert response.json() == []


async def test_list_recipes_public(client: AsyncClient):
    """Guest access: list is public, returns empty list without auth."""
    response = await client.get("/api/recipes")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_recipe_public(client: AsyncClient, authed_client: AsyncClient):
    """Guest access: recipe detail is public."""
    created = await authed_client.post("/api/recipes", json=_sample_recipe_payload())
    recipe_id = created.json()["id"]

    response = await client.get(f"/api/recipes/{recipe_id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Борщ"


# ---------- GLYPH (kind + color) ----------

async def test_create_recipe_with_glyph(authed_client: AsyncClient):
    payload = _sample_recipe_payload("Пицца")
    payload["glyph_kind"] = "pizza"
    payload["glyph_color"] = "red"

    response = await authed_client.post("/api/recipes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["glyph_kind"] == "pizza"
    assert data["glyph_color"] == "red"


async def test_create_recipe_without_glyph_returns_null(authed_client: AsyncClient):
    """Glyph fields default to null when not specified."""
    response = await authed_client.post("/api/recipes", json=_sample_recipe_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["glyph_kind"] is None
    assert data["glyph_color"] is None


async def test_update_recipe_glyph(authed_client: AsyncClient):
    """PUT can set glyph fields."""
    created = await authed_client.post("/api/recipes", json=_sample_recipe_payload())
    recipe_id = created.json()["id"]

    response = await authed_client.put(
        f"/api/recipes/{recipe_id}",
        json={"glyph_kind": "soup", "glyph_color": "green"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["glyph_kind"] == "soup"
    assert data["glyph_color"] == "green"


async def test_update_recipe_clear_glyph(authed_client: AsyncClient):
    """Passing null glyph fields explicitly clears them."""
    payload = _sample_recipe_payload()
    payload["glyph_kind"] = "pizza"
    payload["glyph_color"] = "red"
    created = await authed_client.post("/api/recipes", json=payload)
    recipe_id = created.json()["id"]

    response = await authed_client.put(
        f"/api/recipes/{recipe_id}",
        json={"glyph_kind": None, "glyph_color": None},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["glyph_kind"] is None
    assert data["glyph_color"] is None


async def test_update_recipe_preserves_glyph_when_not_passed(authed_client: AsyncClient):
    """If glyph is not in PUT body, existing values are preserved."""
    payload = _sample_recipe_payload()
    payload["glyph_kind"] = "pizza"
    payload["glyph_color"] = "red"
    created = await authed_client.post("/api/recipes", json=payload)
    recipe_id = created.json()["id"]

    response = await authed_client.put(
        f"/api/recipes/{recipe_id}",
        json={"title": "Пицца обновлённая"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Пицца обновлённая"
    assert data["glyph_kind"] == "pizza"
    assert data["glyph_color"] == "red"


# ---------- PHOTO ----------

async def test_create_recipe_with_photo_url(authed_client: AsyncClient, monkeypatch):
    from app.services import recipe as recipe_service

    async def fake_download(url, recipe_id):
        return f"/api/recipe-images/{recipe_id}.jpg"
    monkeypatch.setattr(recipe_service, "download_recipe_image", fake_download)

    resp = await authed_client.post("/api/recipes", json={
        "title": "Фото-рецепт", "servings": 2, "ingredients": [],
        "photo_url": "https://example.com/x.jpg",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["image_url"].endswith(".jpg")


async def test_create_recipe_photo_download_failure_is_non_fatal(authed_client: AsyncClient, monkeypatch):
    from app.services import recipe as recipe_service

    async def boom(url, recipe_id):
        raise ValueError("bad image")
    monkeypatch.setattr(recipe_service, "download_recipe_image", boom)

    resp = await authed_client.post("/api/recipes", json={
        "title": "Без фото после ошибки", "servings": 2, "ingredients": [],
        "photo_url": "https://example.com/broken",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["image_url"] is None


async def test_update_recipe_clears_photo(authed_client: AsyncClient, monkeypatch):
    from app.services import recipe as recipe_service
    monkeypatch.setattr(recipe_service, "download_recipe_image",
                        lambda url, rid: _async_return(f"/api/recipe-images/{rid}.jpg"))
    deleted = {}
    monkeypatch.setattr(recipe_service, "delete_recipe_image",
                        lambda image_url: deleted.update(url=image_url))

    create = await authed_client.post("/api/recipes", json={
        "title": "Очистка фото", "servings": 2, "ingredients": [],
        "photo_url": "https://example.com/x.jpg",
    })
    rid = create.json()["id"]
    assert create.json()["image_url"].endswith(".jpg")

    upd = await authed_client.put(f"/api/recipes/{rid}", json={"photo_url": ""})
    assert upd.status_code == 200, upd.text
    assert upd.json()["image_url"] is None
    assert deleted["url"].endswith(".jpg")


async def test_update_recipe_replaces_photo_same_extension(authed_client: AsyncClient, monkeypatch, tmp_path):
    """Регресс: при замене фото jpg→jpg image_url не должен указывать на удалённый файл."""
    import httpx

    from app.services import recipe_image

    monkeypatch.setattr(recipe_image.settings, "recipe_images_dir", str(tmp_path))
    # отключаем реальную DNS-проверку и мокаем потоковую загрузку (код использует client.stream)
    async def _noop(*a, **kw):
        return None

    monkeypatch.setattr(recipe_image, "_ensure_public_host", _noop)

    class _Stream:
        def __init__(self, url):
            self._resp = httpx.Response(
                200, content=b"\xff\xd8" + url.encode(),
                headers={"content-type": "image/jpeg"}, request=httpx.Request("GET", url),
            )

        async def __aenter__(self):
            return self._resp

        async def __aexit__(self, *exc):
            return False

    def fake_stream(self, method, url, **kwargs):
        return _Stream(url)

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)

    create = await authed_client.post("/api/recipes", json={
        "title": "Замена фото", "servings": 2, "ingredients": [],
        "photo_url": "https://example.com/old.jpg",
    })
    assert create.status_code == 201, create.text
    rid = create.json()["id"]
    old_url = create.json()["image_url"]

    upd = await authed_client.put(f"/api/recipes/{rid}", json={"photo_url": "https://example.com/new.jpg"})
    assert upd.status_code == 200, upd.text
    new_url = upd.json()["image_url"]
    assert new_url is not None

    new_file = tmp_path / new_url.rsplit("/", 1)[-1]
    assert new_file.exists(), "новый файл фото удалён при замене"
    assert new_file.read_bytes().endswith(b"new.jpg")
    if old_url != new_url:
        assert not (tmp_path / old_url.rsplit("/", 1)[-1]).exists(), "старый файл не подчищен"

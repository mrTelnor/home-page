from httpx import AsyncClient

from app.db.models.user import User


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

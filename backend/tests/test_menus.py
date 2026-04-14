from httpx import AsyncClient

CRON_SECRET = "test-cron-secret"
FAKE_UUID = "00000000-0000-0000-0000-000000000000"


def _sample_recipe(title: str) -> dict:
    return {
        "title": title,
        "description": "desc",
        "servings": 4,
        "ingredients": [{"name": "ing", "amount": "1", "unit": "шт"}],
    }


async def _create_recipes(client: AsyncClient, count: int = 3) -> list[str]:
    ids = []
    for i in range(count):
        r = await client.post("/api/recipes", json=_sample_recipe(f"Recipe {i}"))
        ids.append(r.json()["id"])
    return ids


# ---------- CREATE DAILY ----------

async def test_create_daily_with_admin(admin_client: AsyncClient):
    await _create_recipes(admin_client, 5)

    response = await admin_client.post("/api/menus/create-daily", json={})
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "collecting"
    assert len(data["recipes"]) == 3  # min(3, 5)


async def test_create_daily_with_cron_secret(
    client: AsyncClient, admin_client: AsyncClient
):
    await _create_recipes(admin_client, 5)

    response = await client.post(
        "/api/menus/create-daily",
        headers={"X-Cron-Secret": CRON_SECRET},
        json={},
    )
    assert response.status_code == 201


async def test_create_daily_forbidden_for_user(authed_client: AsyncClient):
    response = await authed_client.post("/api/menus/create-daily", json={})
    assert response.status_code == 403


async def test_create_daily_duplicate(admin_client: AsyncClient):
    await _create_recipes(admin_client, 3)
    await admin_client.post("/api/menus/create-daily", json={})

    response = await admin_client.post("/api/menus/create-daily", json={})
    assert response.status_code == 409


# ---------- SUGGEST ----------

async def test_suggest_recipe(authed_client: AsyncClient, admin_client: AsyncClient):
    recipe_ids = await _create_recipes(admin_client, 5)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()
    menu_recipe_ids = {r["recipe_id"] for r in menu["recipes"]}
    extra_recipe = next(rid for rid in recipe_ids if rid not in menu_recipe_ids)

    response = await authed_client.post(
        f"/api/menus/{menu['id']}/suggest",
        json={"recipe_id": extra_recipe},
    )
    assert response.status_code == 200
    suggested = [r for r in response.json()["recipes"] if r["source"] == "user"]
    assert len(suggested) == 1


async def test_suggest_user_limit(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    recipe_ids = await _create_recipes(admin_client, 10)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()
    menu_recipe_ids = {r["recipe_id"] for r in menu["recipes"]}
    extras = [rid for rid in recipe_ids if rid not in menu_recipe_ids]

    # Первое предложение проходит
    r1 = await authed_client.post(
        f"/api/menus/{menu['id']}/suggest",
        json={"recipe_id": extras[0]},
    )
    assert r1.status_code == 200

    # Второе — 400 (лимит)
    r2 = await authed_client.post(
        f"/api/menus/{menu['id']}/suggest",
        json={"recipe_id": extras[1]},
    )
    assert r2.status_code == 400


# ---------- FULL VOTING CYCLE ----------

async def test_full_voting_cycle(
    admin_client: AsyncClient, authed_client: AsyncClient
):
    await _create_recipes(admin_client, 3)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()
    menu_id = menu["id"]
    recipe_id = menu["recipes"][0]["recipe_id"]

    # Финализация (открыть голосование)
    r = await admin_client.post("/api/menus/finalize", json={})
    assert r.status_code == 200
    assert r.json()["status"] == "voting"

    # Голос — authed_client
    r = await authed_client.post(
        f"/api/menus/{menu_id}/vote",
        json={"recipe_id": recipe_id},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_votes"] == 1
    assert data["user_voted_recipe_id"] == recipe_id

    # Повторный голос — 409
    r = await authed_client.post(
        f"/api/menus/{menu_id}/vote",
        json={"recipe_id": recipe_id},
    )
    assert r.status_code == 409

    # Отмена голоса
    r = await authed_client.delete(f"/api/menus/{menu_id}/vote")
    assert r.status_code == 200
    assert r.json()["total_votes"] == 0
    assert r.json()["user_voted_recipe_id"] is None

    # Голос admin, потом закрытие — победитель определён
    r = await admin_client.post(
        f"/api/menus/{menu_id}/vote",
        json={"recipe_id": recipe_id},
    )
    assert r.status_code == 200

    r = await admin_client.post("/api/menus/close-voting", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "closed"
    assert data["winner_recipe_id"] == recipe_id


async def test_vote_when_collecting_fails(
    admin_client: AsyncClient, authed_client: AsyncClient
):
    await _create_recipes(admin_client, 3)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()
    recipe_id = menu["recipes"][0]["recipe_id"]

    r = await authed_client.post(
        f"/api/menus/{menu['id']}/vote",
        json={"recipe_id": recipe_id},
    )
    assert r.status_code == 400


async def test_today_endpoint(
    admin_client: AsyncClient, authed_client: AsyncClient
):
    await _create_recipes(admin_client, 3)
    await admin_client.post("/api/menus/create-daily", json={})

    r = await authed_client.get("/api/menus/today")
    assert r.status_code == 200
    assert r.json()["status"] == "collecting"


async def test_today_not_found(authed_client: AsyncClient):
    r = await authed_client.get("/api/menus/today")
    assert r.status_code == 404


# ---------- DELETE (admin) ----------

async def test_delete_menu_admin(admin_client: AsyncClient):
    await _create_recipes(admin_client, 3)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()

    r = await admin_client.delete(f"/api/menus/{menu['id']}")
    assert r.status_code == 204


async def test_delete_menu_user_forbidden(
    admin_client: AsyncClient, authed_client: AsyncClient
):
    await _create_recipes(admin_client, 3)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()

    r = await authed_client.delete(f"/api/menus/{menu['id']}")
    assert r.status_code == 403


async def test_delete_menu_not_found(admin_client: AsyncClient):
    r = await admin_client.delete(f"/api/menus/{FAKE_UUID}")
    assert r.status_code == 404


# ---------- SUGGEST ERRORS ----------

async def test_suggest_menu_not_found(authed_client: AsyncClient):
    r = await authed_client.post(
        f"/api/menus/{FAKE_UUID}/suggest",
        json={"recipe_id": FAKE_UUID},
    )
    assert r.status_code == 404


async def test_suggest_recipe_not_found(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    await _create_recipes(admin_client, 3)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()

    r = await authed_client.post(
        f"/api/menus/{menu['id']}/suggest",
        json={"recipe_id": FAKE_UUID},
    )
    assert r.status_code == 404


async def test_suggest_recipe_already_in_menu(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    await _create_recipes(admin_client, 3)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()
    existing_recipe_id = menu["recipes"][0]["recipe_id"]

    r = await authed_client.post(
        f"/api/menus/{menu['id']}/suggest",
        json={"recipe_id": existing_recipe_id},
    )
    assert r.status_code == 409


async def test_suggest_menu_not_collecting(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    recipe_ids = await _create_recipes(admin_client, 5)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()
    menu_recipe_ids = {r["recipe_id"] for r in menu["recipes"]}
    extra = next(rid for rid in recipe_ids if rid not in menu_recipe_ids)

    await admin_client.post("/api/menus/finalize", json={})

    r = await authed_client.post(
        f"/api/menus/{menu['id']}/suggest",
        json={"recipe_id": extra},
    )
    assert r.status_code == 400


# ---------- VOTE ERRORS ----------

async def test_vote_recipe_not_in_menu(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    await _create_recipes(admin_client, 3)
    await admin_client.post("/api/menus/create-daily", json={})
    menu = (await admin_client.post("/api/menus/finalize", json={})).json()

    r = await authed_client.post(
        f"/api/menus/{menu['id']}/vote",
        json={"recipe_id": FAKE_UUID},
    )
    assert r.status_code == 400


# ---------- FINALIZE / CLOSE ERRORS ----------

async def test_finalize_menu_not_found(admin_client: AsyncClient):
    r = await admin_client.post(
        "/api/menus/finalize", json={"date": "2000-01-01"}
    )
    assert r.status_code == 404


async def test_close_voting_menu_not_found(admin_client: AsyncClient):
    r = await admin_client.post(
        "/api/menus/close-voting", json={"date": "2000-01-01"}
    )
    assert r.status_code == 404


async def test_close_voting_not_in_voting_status(admin_client: AsyncClient):
    await _create_recipes(admin_client, 3)
    await admin_client.post("/api/menus/create-daily", json={})

    r = await admin_client.post("/api/menus/close-voting", json={})
    assert r.status_code == 400


# ---------- GET ONE / LIST ----------

async def test_get_menu_by_id(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    await _create_recipes(admin_client, 3)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()

    r = await authed_client.get(f"/api/menus/{menu['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == menu["id"]


async def test_get_menu_not_found(authed_client: AsyncClient):
    r = await authed_client.get(f"/api/menus/{FAKE_UUID}")
    assert r.status_code == 404


async def test_list_menus(
    authed_client: AsyncClient, admin_client: AsyncClient
):
    await _create_recipes(admin_client, 3)
    await admin_client.post("/api/menus/create-daily", json={})

    r = await authed_client.get("/api/menus")
    assert r.status_code == 200
    assert len(r.json()) >= 1

"""Гонки и целостность menu-флоу: каскады удаления, дубли предложений,
конкурентные create-daily/close-voting.

API-тесты — через клиентов conftest; сервисные — напрямую через TestSessionMaker.
"""
from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models.menu import DailyMenu, DailyMenuRecipe, Vote
from app.db.models.recipe import Recipe
from app.services.menu import close_voting, get_menu_by_id, suggest_recipe
from tests.conftest import TestSessionMaker, _create_user_standalone

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
        r = await client.post("/api/recipes", json=_sample_recipe(f"Race Recipe {i}"))
        ids.append(r.json()["id"])
    return ids


# ---------- DELETE menu с голосами ----------


async def test_delete_menu_with_votes(admin_client: AsyncClient, authed_client: AsyncClient):
    """Удаление меню, за которое голосовали, — 204, а не 500 (FK votes без cascade)."""
    await _create_recipes(admin_client, 3)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()
    await admin_client.post("/api/menus/finalize", json={})
    r = await authed_client.post(
        f"/api/menus/{menu['id']}/vote", json={"recipe_id": menu["recipes"][0]["recipe_id"]}
    )
    assert r.status_code == 200

    r = await admin_client.delete(f"/api/menus/{menu['id']}")
    assert r.status_code == 204

    # Рецепты при этом не пострадали
    r = await admin_client.get("/api/recipes")
    assert len(r.json()) == 3


# ---------- DELETE рецепта, задействованного в меню ----------


async def test_delete_recipe_in_collecting_menu_conflict(admin_client: AsyncClient):
    """Рецепт в меню со статусом collecting: 409, а не 500 (раньше проверялся только voting)."""
    await _create_recipes(admin_client, 3)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()
    recipe_id = menu["recipes"][0]["recipe_id"]

    r = await admin_client.delete(f"/api/recipes/{recipe_id}")
    assert r.status_code == 409


async def test_delete_recipe_in_closed_menu_conflict(
    admin_client: AsyncClient, authed_client: AsyncClient
):
    """Рецепт-победитель закрытого меню: 409, а не 500."""
    await _create_recipes(admin_client, 3)
    menu = (await admin_client.post("/api/menus/create-daily", json={})).json()
    recipe_id = menu["recipes"][0]["recipe_id"]
    await admin_client.post("/api/menus/finalize", json={})
    await authed_client.post(f"/api/menus/{menu['id']}/vote", json={"recipe_id": recipe_id})
    closed = (await admin_client.post("/api/menus/close-voting", json={})).json()
    assert closed["winner_recipe_id"] == recipe_id

    r = await admin_client.delete(f"/api/recipes/{recipe_id}")
    assert r.status_code == 409


# ---------- Дубль предложения (гонка мимо check-then-insert) ----------


async def test_suggest_duplicate_blocked_by_constraint():
    """UNIQUE(menu_id, recipe_id): дубль, проскочивший мимо проверки роутера
    (гонка двух параллельных suggest), должен упереться в констрейнт БД."""
    author = await _create_user_standalone("race_author")
    async with TestSessionMaker() as session:
        recipe = Recipe(id=uuid4(), title="Гонка", description=None, servings=2, author_id=author.id)
        session.add(recipe)
        menu = DailyMenu(id=uuid4(), date=date(2026, 3, 1), status="collecting")
        session.add(menu)
        await session.commit()
        await session.refresh(menu, ["menu_recipes"])

        # max_suggestions=3: лимит не мешает, дубль должен поймать именно констрейнт
        await suggest_recipe(session, menu, recipe.id, author.id, max_suggestions=3)
        with pytest.raises(IntegrityError):
            await suggest_recipe(session, menu, recipe.id, author.id, max_suggestions=3)


# ---------- create-daily: гонка двух вызовов ----------


async def test_create_daily_race_returns_409(admin_client: AsyncClient, monkeypatch):
    """Если оба конкурентных вызова прошли проверку get_menu_by_date (оба увидели
    'меню нет'), проигравший должен получить 409, а не 500."""
    from unittest.mock import AsyncMock

    from app.api import menus as menus_api

    await _create_recipes(admin_client, 3)
    r1 = await admin_client.post("/api/menus/create-daily", json={})
    assert r1.status_code == 201

    # Имитируем гонку: проверка «меню уже есть» вернула None, вставка упрётся в UNIQUE(date)
    monkeypatch.setattr(menus_api, "get_menu_by_date", AsyncMock(return_value=None))
    r2 = await admin_client.post("/api/menus/create-daily", json={})
    assert r2.status_code == 409


# ---------- close-voting: победитель не пересчитывается вторым вызовом ----------


async def test_close_voting_stale_object_does_not_recompute():
    """Гонка двух close-voting: второй вызов с устаревшим объектом (в памяти ещё
    status=voting) не должен пересчитывать победителя — статус перечитывается
    из БД под блокировкой."""
    author = await _create_user_standalone("race_closer")
    voter = await _create_user_standalone("race_voter")
    async with TestSessionMaker() as session:
        r1 = Recipe(id=uuid4(), title="А", description=None, servings=2, author_id=author.id)
        r2 = Recipe(id=uuid4(), title="Б", description=None, servings=2, author_id=author.id)
        session.add_all([r1, r2])
        await session.flush()  # рецепты существуют до голоса (как в реальном флоу)
        menu = DailyMenu(id=uuid4(), date=date(2026, 3, 2), status="voting")
        menu.menu_recipes.append(
            DailyMenuRecipe(id=uuid4(), recipe_id=r1.id, source="random", added_by=None)
        )
        menu.menu_recipes.append(
            DailyMenuRecipe(id=uuid4(), recipe_id=r2.id, source="random", added_by=None)
        )
        session.add(menu)
        # Единственный голос за r1 — победитель детерминирован
        session.add(Vote(id=uuid4(), menu_id=menu.id, recipe_id=r1.id, user_id=voter.id))
        await session.commit()
        await session.refresh(menu, ["menu_recipes"])

        menu_id = menu.id
        r1_id, r2_id = r1.id, r2.id

    # Конкурент читает меню, пока оно ещё voting (чистый объект, без ручных правок)
    session2 = TestSessionMaker()
    stale = await get_menu_by_id(session2, menu_id)
    assert stale.status == "voting"

    # Первый вызов закрывает голосование: победитель r1 (единственный голос)
    async with TestSessionMaker() as session1:
        menu1 = await get_menu_by_id(session1, menu_id)
        first = await close_voting(session1, menu1)
        assert first.status == "closed"
        assert first.winner_recipe_id == r1_id
        # Голос переставлен на r2 ПОСЛЕ закрытия — пересчёт дал бы r2
        vote = (await session1.execute(select(Vote).where(Vote.menu_id == menu_id))).scalar_one()
        vote.recipe_id = r2_id
        await session1.commit()

    # Второй вызов на устаревшем (но не грязном) объекте: FOR UPDATE + populate_existing
    # перечитывают closed из БД → победитель не пересчитывается
    try:
        second = await close_voting(session2, stale)
        assert second.status == "closed"
        assert second.winner_recipe_id == r1_id, "второй close-voting пересчитал победителя"
    finally:
        await session2.close()

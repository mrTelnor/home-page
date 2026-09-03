"""GET /api/menus не должен расти по числу SQL-запросов линейно от числа меню (N+1)."""
from httpx import AsyncClient
from sqlalchemy import event

from tests.conftest import test_engine


def _sample_recipe(title: str) -> dict:
    return {"title": title, "servings": 2, "ingredients": [{"name": "x", "amount": "1", "unit": "шт"}]}


class _QueryCounter:
    def __init__(self):
        self.count = 0

    def __enter__(self):
        sync_engine = test_engine.sync_engine

        def _before(conn, cursor, statement, params, context, executemany):
            self.count += 1

        self._handler = _before
        event.listen(sync_engine, "before_cursor_execute", self._handler)
        return self

    def __exit__(self, *exc):
        event.remove(test_engine.sync_engine, "before_cursor_execute", self._handler)


async def _make_menus(admin_client: AsyncClient, n: int, start_day: int = 0) -> None:
    """Создаёт n закрытых меню на разные даты через сервисный слой (быстрее HTTP-цикла)."""
    from datetime import date, timedelta
    from uuid import uuid4

    from app.db.models.menu import DailyMenu, DailyMenuRecipe, Vote
    from app.db.models.recipe import Recipe
    from tests.conftest import TestSessionMaker, _create_user_standalone

    author = await _create_user_standalone(f"perf_{uuid4().hex[:6]}")
    voter = await _create_user_standalone(f"perfv_{uuid4().hex[:6]}")
    async with TestSessionMaker() as s:
        recipes = [Recipe(id=uuid4(), title=f"R{i}", servings=2, author_id=author.id) for i in range(3)]
        s.add_all(recipes)
        await s.flush()
        base = date(2026, 1, 1)
        for d in range(start_day, start_day + n):
            menu = DailyMenu(id=uuid4(), date=base + timedelta(days=d), status="closed",
                             winner_recipe_id=recipes[0].id)
            for r in recipes:
                menu.menu_recipes.append(
                    DailyMenuRecipe(id=uuid4(), recipe_id=r.id, source="random", added_by=None)
                )
            s.add(menu)
            s.add(Vote(id=uuid4(), menu_id=menu.id, recipe_id=recipes[0].id, user_id=voter.id))
        await s.commit()


async def test_list_menus_query_count_is_bounded(admin_client: AsyncClient):
    """Число запросов на GET /api/menus не должно линейно расти с числом меню."""
    await _make_menus(admin_client, 3)
    with _QueryCounter() as c3:
        r = await admin_client.get("/api/menus")
    assert r.status_code == 200
    assert len(r.json()) == 3
    small = c3.count

    await _make_menus(admin_client, 9, start_day=3)  # теперь 12 меню, даты не пересекаются
    with _QueryCounter() as c12:
        r = await admin_client.get("/api/menus")
    assert r.status_code == 200
    assert len(r.json()) == 12
    large = c12.count

    # При N+1 large ≈ small + 9*(запросов на меню). Требуем, чтобы рост был мал.
    assert large - small <= 2, f"N+1: {small} → {large} запросов при росте меню 3→12"


async def test_list_menus_pagination(admin_client: AsyncClient):
    """limit/offset ограничивают выборку, порядок — свежие сверху (по дате desc)."""
    await _make_menus(admin_client, 5)
    r = await admin_client.get("/api/menus?limit=2")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    # свежайшая дата — первая
    assert body[0]["date"] > body[1]["date"]

    r2 = await admin_client.get("/api/menus?limit=2&offset=2")
    assert len(r2.json()) == 2
    assert r2.json()[0]["date"] < body[1]["date"]

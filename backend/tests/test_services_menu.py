"""
Unit/edge-тесты сервис-слоя меню (app/services/menu.py, app/services/recipe.py).

Работают напрямую с AsyncSession (без HTTP-клиента), используют
TestSessionMaker и _create_user_standalone из conftest.
Фикстуры setup_database / clean_tables из conftest применяются автоматически.

ВАЖНО (зафиксировано по коду app/services/menu.py):
- close_voting разруливает ничью через secrets.choice(candidates) —
  выбор СЛУЧАЙНЫЙ среди рецептов с максимумом голосов, НЕ детерминированный.
  Гарантируется только то, что победитель входит в множество лидеров.
- create_daily_menu НЕ идемпотентен: повторный вызов за ту же дату падает
  IntegrityError (уникальность DailyMenu.date); 409 отдаёт роутер, не сервис.
- cast_vote НЕ проверяет повторное голосование: второй голос того же
  пользователя падает IntegrityError (uq_vote_user_menu).
"""

from collections.abc import AsyncGenerator
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.menu import DailyMenu, DailyMenuRecipe, Vote
from app.db.models.recipe import Ingredient, Recipe
from app.db.models.user import User
from app.services.menu import (
    cast_vote,
    close_voting,
    create_daily_menu,
    get_menu_by_id,
    get_votes_for_menu,
)
from app.services.recipe import delete_recipe, get_recipe_by_id
from tests.conftest import TestSessionMaker, _create_user_standalone

MENU_DATE = date(2026, 1, 15)


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Прямая сессия к тестовой БД (как в _override_get_db, но без HTTP-слоя)."""
    async with TestSessionMaker() as s:
        yield s


@pytest.fixture
async def author() -> User:
    """Автор рецептов (FK recipes.author_id)."""
    return await _create_user_standalone("svc_author")


async def _create_recipe(session: AsyncSession, title: str, author_id: UUID) -> Recipe:
    recipe = Recipe(id=uuid4(), title=title, description=None, servings=4, author_id=author_id)
    session.add(recipe)
    await session.commit()
    return recipe


async def _create_menu_with_recipes(
    session: AsyncSession, recipes: list[Recipe], menu_date: date = MENU_DATE, status: str = "voting"
) -> DailyMenu:
    """Меню с заранее известным набором рецептов (create_daily_menu выбирает случайно)."""
    menu = DailyMenu(id=uuid4(), date=menu_date, status=status)
    for recipe in recipes:
        menu.menu_recipes.append(
            DailyMenuRecipe(id=uuid4(), recipe_id=recipe.id, source="random", added_by=None)
        )
    session.add(menu)
    await session.commit()
    return menu


# ---------- close_voting ----------

async def test_close_voting_picks_recipe_with_most_votes(session: AsyncSession, author: User):
    """3 рецепта, голоса 2/1/0 — побеждает рецепт с максимумом (menu.py:146-148)."""
    recipes = [await _create_recipe(session, f"R{i}", author.id) for i in range(3)]
    menu = await _create_menu_with_recipes(session, recipes)
    voters = [await _create_user_standalone(f"svc_voter{i}") for i in range(3)]

    await cast_vote(session, menu.id, recipes[0].id, voters[0].id)
    await cast_vote(session, menu.id, recipes[0].id, voters[1].id)
    await cast_vote(session, menu.id, recipes[1].id, voters[2].id)

    closed = await close_voting(session, menu)

    assert closed.status == "closed"
    assert closed.winner_recipe_id == recipes[0].id

    votes = await get_votes_for_menu(session, menu.id)
    assert votes == {recipes[0].id: 2, recipes[1].id: 1}


async def test_close_voting_tie_winner_is_one_of_leaders(session: AsyncSession, author: User):
    """Ничья 1/1/0: победитель — secrets.choice среди лидеров (menu.py:147-148).

    Выбор СЛУЧАЙНЫЙ, между вызовами НЕ детерминирован — гарантируем только
    принадлежность множеству лидеров и что аутсайдер (0 голосов) не выигрывает.
    Сервис не защищает от повторного закрытия (это делает роутер по статусу):
    повторный вызов на тех же голосах снова даёт победителя из того же множества.
    """
    recipes = [await _create_recipe(session, f"T{i}", author.id) for i in range(3)]
    menu = await _create_menu_with_recipes(session, recipes)
    voter_a = await _create_user_standalone("svc_tie_a")
    voter_b = await _create_user_standalone("svc_tie_b")

    await cast_vote(session, menu.id, recipes[0].id, voter_a.id)
    await cast_vote(session, menu.id, recipes[1].id, voter_b.id)

    leaders = {recipes[0].id, recipes[1].id}

    closed = await close_voting(session, menu)
    assert closed.status == "closed"
    assert closed.winner_recipe_id in leaders
    assert closed.winner_recipe_id != recipes[2].id

    # Повторный вызов на тех же данных: победитель может смениться (random),
    # но всегда остаётся в множестве лидеров — фиксируем фактический контракт.
    reclosed = await close_voting(session, menu)
    assert reclosed.winner_recipe_id in leaders


async def test_close_voting_without_votes_picks_any_menu_recipe(session: AsyncSession, author: User):
    """Без голосов: max_votes=0, кандидаты — ВСЕ рецепты меню, победитель случайный
    из них (menu.py:146-148). Не падает, статус closed, победитель назначен."""
    recipes = [await _create_recipe(session, f"N{i}", author.id) for i in range(3)]
    menu = await _create_menu_with_recipes(session, recipes)

    closed = await close_voting(session, menu)

    assert closed.status == "closed"
    assert closed.winner_recipe_id in {r.id for r in recipes}


async def test_close_voting_empty_menu_no_winner(session: AsyncSession):
    """Меню вообще без рецептов: ранний выход (menu.py:140-144) —
    статус closed, winner_recipe_id остаётся None."""
    menu = DailyMenu(id=uuid4(), date=MENU_DATE, status="voting")
    session.add(menu)
    await session.commit()
    menu_id = menu.id

    # Как в продакшене: роутер берёт меню из get_menu_by_id (selectinload
    # menu_recipes). У свежесозданного объекта пустая коллекция после commit
    # не считается загруженной, и close_voting упёрся бы в async lazy-load
    # (MissingGreenlet).
    menu = await get_menu_by_id(session, menu_id)
    assert menu is not None
    assert menu.menu_recipes == []

    closed = await close_voting(session, menu)

    assert closed.status == "closed"
    assert closed.winner_recipe_id is None


# ---------- create_daily_menu ----------

async def test_create_daily_menu_with_empty_recipe_db(session: AsyncSession):
    """Пустая база рецептов: rng.sample([], 0) → меню создаётся БЕЗ рецептов,
    без ошибки (menu.py:41-47). Статус collecting."""
    menu = await create_daily_menu(session, MENU_DATE)

    assert menu.status == "collecting"
    assert menu.date == MENU_DATE
    assert menu.menu_recipes == []


async def test_create_daily_menu_duplicate_date_raises(session: AsyncSession, author: User):
    """Сервис НЕ идемпотентен: повторный вызов за ту же дату нарушает
    уникальность DailyMenu.date (models/menu.py:18) → IntegrityError.
    Проверку «меню уже есть» делает роутер (409), не сервис."""
    await _create_recipe(session, "Dup", author.id)
    first = await create_daily_menu(session, MENU_DATE)
    assert first.date == MENU_DATE
    # rollback() экспайрит ВСЕ объекты сессии, а lazy-load в async-сессии
    # вне greenlet-контекста падает MissingGreenlet — id снимаем заранее
    first_id = first.id

    with pytest.raises(IntegrityError):
        await create_daily_menu(session, MENU_DATE)
    await session.rollback()

    # Первое меню не пострадало
    result = await session.execute(select(DailyMenu).where(DailyMenu.date == MENU_DATE))
    menus = result.scalars().all()
    assert len(menus) == 1
    assert menus[0].id == first_id


async def test_create_daily_menu_picks_at_most_three(session: AsyncSession, author: User):
    """min(3, len(all)) рецептов, source='random' (menu.py:44-51)."""
    for i in range(5):
        await _create_recipe(session, f"P{i}", author.id)

    menu = await create_daily_menu(session, MENU_DATE)

    assert len(menu.menu_recipes) == 3
    assert all(mr.source == "random" and mr.added_by is None for mr in menu.menu_recipes)
    # Без повторов
    assert len({mr.recipe_id for mr in menu.menu_recipes}) == 3


# ---------- cast_vote ----------

async def test_cast_vote_twice_same_user_raises(session: AsyncSession, author: User):
    """Повторный голос того же пользователя в том же меню нарушает
    uq_vote_user_menu (models/menu.py:39-42) → IntegrityError на commit.
    Сервис cast_vote (menu.py:101-107) сам ничего не проверяет."""
    recipes = [await _create_recipe(session, f"V{i}", author.id) for i in range(2)]
    menu = await _create_menu_with_recipes(session, recipes)
    voter = await _create_user_standalone("svc_double_voter")
    # id снимаем до rollback: после него объекты протухают, а async lazy-load
    # вне greenlet-контекста падает MissingGreenlet
    menu_id = menu.id

    await cast_vote(session, menu_id, recipes[0].id, voter.id)

    # Даже за ДРУГОЙ рецепт — constraint по (user_id, menu_id)
    with pytest.raises(IntegrityError):
        await cast_vote(session, menu_id, recipes[1].id, voter.id)
    await session.rollback()

    result = await session.execute(select(Vote).where(Vote.menu_id == menu_id))
    assert len(result.scalars().all()) == 1


# ---------- delete_recipe (services/recipe.py) ----------

async def test_delete_recipe_in_menu_blocked_by_fk(session: AsyncSession, author: User):
    """Рецепт, состоящий в меню, удалить нельзя: FK daily_menu_recipes.recipe_id
    задан БЕЗ ondelete (models/menu.py:30), у Recipe нет relationship на
    DailyMenuRecipe → Postgres кидает FK violation (IntegrityError) на commit.
    CI-ревью: поведение опирается на серверный FK (NO ACTION) — проверяется только на Postgres.
    """
    recipe = await _create_recipe(session, "InMenu", author.id)
    menu = await _create_menu_with_recipes(session, [recipe])
    # id снимаем до rollback: после него объекты протухают, а async lazy-load
    # вне greenlet-контекста падает MissingGreenlet
    recipe_id = recipe.id
    menu_id = menu.id

    with pytest.raises(IntegrityError):
        await delete_recipe(session, recipe)
    await session.rollback()

    # Рецепт и связь с меню на месте
    assert await get_recipe_by_id(session, recipe_id) is not None
    result = await session.execute(select(DailyMenuRecipe).where(DailyMenuRecipe.menu_id == menu_id))
    assert len(result.scalars().all()) == 1


async def test_delete_recipe_not_in_menu_cascades_ingredients(session: AsyncSession, author: User):
    """Рецепт вне меню удаляется, ингредиенты уходят каскадом:
    ORM cascade='all, delete-orphan' (models/recipe.py:22) +
    FK ingredients.recipe_id ondelete='CASCADE' (models/recipe.py:29)."""
    recipe = Recipe(id=uuid4(), title="Free", description=None, servings=2, author_id=author.id)
    recipe.ingredients.append(Ingredient(id=uuid4(), name="ing", amount="1", unit="шт"))
    session.add(recipe)
    await session.commit()
    recipe_id = recipe.id

    await delete_recipe(session, recipe)

    assert await get_recipe_by_id(session, recipe_id) is None
    result = await session.execute(select(Ingredient).where(Ingredient.recipe_id == recipe_id))
    assert result.scalars().all() == []

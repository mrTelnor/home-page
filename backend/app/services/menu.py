import random
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.menu import DailyMenu, DailyMenuRecipe, Vote
from app.db.models.recipe import Recipe


async def get_menu_by_date(session: AsyncSession, menu_date: date) -> DailyMenu | None:
    result = await session.execute(
        select(DailyMenu)
        .where(DailyMenu.date == menu_date)
        .options(selectinload(DailyMenu.menu_recipes))
    )
    return result.scalar_one_or_none()


async def get_menu_by_id(session: AsyncSession, menu_id: uuid.UUID) -> DailyMenu | None:
    result = await session.execute(
        select(DailyMenu)
        .where(DailyMenu.id == menu_id)
        .options(selectinload(DailyMenu.menu_recipes))
    )
    return result.scalar_one_or_none()


async def get_all_menus(session: AsyncSession) -> list[DailyMenu]:
    result = await session.execute(
        select(DailyMenu)
        .options(selectinload(DailyMenu.menu_recipes))
        .order_by(DailyMenu.date.desc())
    )
    return list(result.scalars().all())


async def create_daily_menu(session: AsyncSession, menu_date: date) -> DailyMenu:
    result = await session.execute(select(Recipe.id))
    all_recipe_ids = [row[0] for row in result.all()]

    random_ids = random.sample(all_recipe_ids, min(3, len(all_recipe_ids)))

    menu = DailyMenu(id=uuid.uuid4(), date=menu_date, status="collecting")
    for recipe_id in random_ids:
        menu.menu_recipes.append(
            DailyMenuRecipe(id=uuid.uuid4(), recipe_id=recipe_id, source="random", added_by=None)
        )
    session.add(menu)
    await session.commit()
    await session.refresh(menu, ["menu_recipes"])
    return menu


async def suggest_recipe(
    session: AsyncSession, menu: DailyMenu, recipe_id: uuid.UUID, user_id: uuid.UUID
) -> DailyMenuRecipe:
    menu_recipe = DailyMenuRecipe(
        id=uuid.uuid4(), menu_id=menu.id, recipe_id=recipe_id, source="user", added_by=user_id
    )
    session.add(menu_recipe)
    await session.commit()
    await session.refresh(menu_recipe)
    return menu_recipe


async def count_user_suggestions(session: AsyncSession, menu_id: uuid.UUID, user_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(DailyMenuRecipe)
        .where(
            DailyMenuRecipe.menu_id == menu_id,
            DailyMenuRecipe.added_by == user_id,
            DailyMenuRecipe.source == "user",
        )
    )
    return result.scalar_one()


async def is_recipe_in_menu(session: AsyncSession, menu_id: uuid.UUID, recipe_id: uuid.UUID) -> bool:
    result = await session.execute(
        select(DailyMenuRecipe).where(
            DailyMenuRecipe.menu_id == menu_id, DailyMenuRecipe.recipe_id == recipe_id
        )
    )
    return result.scalar_one_or_none() is not None


async def finalize_menu(session: AsyncSession, menu: DailyMenu) -> DailyMenu:
    menu.status = "voting"
    await session.commit()
    await session.refresh(menu, ["menu_recipes"])
    return menu


async def cast_vote(
    session: AsyncSession, menu_id: uuid.UUID, recipe_id: uuid.UUID, user_id: uuid.UUID
) -> Vote:
    vote = Vote(id=uuid.uuid4(), menu_id=menu_id, recipe_id=recipe_id, user_id=user_id)
    session.add(vote)
    await session.commit()
    return vote


async def close_voting(session: AsyncSession, menu: DailyMenu) -> DailyMenu:
    result = await session.execute(
        select(Vote.recipe_id, func.count().label("cnt"))
        .where(Vote.menu_id == menu.id)
        .group_by(Vote.recipe_id)
    )
    vote_counts = {row.recipe_id: row.cnt for row in result.all()}

    menu_recipe_ids = [mr.recipe_id for mr in menu.menu_recipes]

    if not menu_recipe_ids:
        menu.status = "closed"
        await session.commit()
        await session.refresh(menu, ["menu_recipes"])
        return menu

    max_votes = max((vote_counts.get(rid, 0) for rid in menu_recipe_ids), default=0)
    candidates = [rid for rid in menu_recipe_ids if vote_counts.get(rid, 0) == max_votes]
    winner = random.choice(candidates)

    menu.winner_recipe_id = winner
    menu.status = "closed"
    await session.commit()
    await session.refresh(menu, ["menu_recipes"])
    return menu


async def get_votes_for_menu(session: AsyncSession, menu_id: uuid.UUID) -> dict[uuid.UUID, int]:
    result = await session.execute(
        select(Vote.recipe_id, func.count().label("cnt"))
        .where(Vote.menu_id == menu_id)
        .group_by(Vote.recipe_id)
    )
    return {row.recipe_id: row.cnt for row in result.all()}


async def delete_menu(session: AsyncSession, menu: DailyMenu) -> None:
    await session.delete(menu)
    await session.commit()


async def recipe_exists(session: AsyncSession, recipe_id: uuid.UUID) -> bool:
    result = await session.execute(select(Recipe.id).where(Recipe.id == recipe_id))
    return result.scalar_one_or_none() is not None

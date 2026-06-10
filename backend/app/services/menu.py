import secrets
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.menu import DailyMenu, DailyMenuRecipe, Vote
from app.db.models.recipe import Recipe
from app.schemas.menu import MenuRecipeResponse, MenuResponse


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

    rng = secrets.SystemRandom()
    random_ids = rng.sample(all_recipe_ids, min(3, len(all_recipe_ids)))

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
    # Инвалидируем кэш menu, чтобы последующий get_menu_by_id вернул актуальную коллекцию
    await session.refresh(menu, ["menu_recipes"])
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


async def get_user_vote(
    session: AsyncSession, menu_id: uuid.UUID, user_id: uuid.UUID
) -> Vote | None:
    result = await session.execute(
        select(Vote).where(Vote.menu_id == menu_id, Vote.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def cancel_vote(
    session: AsyncSession, menu_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    vote = await get_user_vote(session, menu_id, user_id)
    if vote is None:
        return False
    await session.delete(vote)
    await session.commit()
    return True


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
    winner = secrets.choice(candidates)

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


async def get_voters_for_menu(session: AsyncSession, menu_id: uuid.UUID) -> dict[uuid.UUID, list]:
    """Return dict {recipe_id: [User, User, ...]} for all votes in the menu."""
    from app.db.models.user import User

    result = await session.execute(
        select(Vote.recipe_id, User)
        .join(User, User.id == Vote.user_id)
        .where(Vote.menu_id == menu_id)
        .order_by(User.first_name, User.username)
    )
    voters: dict[uuid.UUID, list] = {}
    for recipe_id, user in result.all():
        voters.setdefault(recipe_id, []).append(user)
    return voters


async def build_menu_response(
    session: AsyncSession, menu: DailyMenu, user_id: uuid.UUID | None = None
) -> MenuResponse:
    is_collecting = menu.status == "collecting"
    vote_counts = await get_votes_for_menu(session, menu.id) if not is_collecting else {}
    voters_by_recipe = await get_voters_for_menu(session, menu.id) if not is_collecting else {}

    # Один запрос на все рецепты меню вместо запроса на каждый
    recipe_ids = [mr.recipe_id for mr in menu.menu_recipes]
    recipes_by_id: dict[uuid.UUID, Recipe] = {}
    if recipe_ids:
        result = await session.execute(select(Recipe).where(Recipe.id.in_(recipe_ids)))
        recipes_by_id = {r.id: r for r in result.scalars().all()}

    recipes = []
    for mr in menu.menu_recipes:
        recipe = recipes_by_id.get(mr.recipe_id)
        recipe_voters = voters_by_recipe.get(mr.recipe_id, [])
        recipes.append(
            MenuRecipeResponse(
                id=mr.id,
                recipe_id=mr.recipe_id,
                title=recipe.title if recipe else "Deleted recipe",
                source=mr.source,
                added_by=mr.added_by,
                votes_count=vote_counts.get(mr.recipe_id, 0),
                voters=[
                    {"id": v.id, "first_name": v.first_name, "username": v.username}
                    for v in recipe_voters
                ],
            )
        )

    user_voted_recipe_id = None
    if user_id is not None and not is_collecting:
        user_vote = await get_user_vote(session, menu.id, user_id)
        if user_vote:
            user_voted_recipe_id = user_vote.recipe_id

    return MenuResponse(
        id=menu.id,
        date=menu.date,
        status=menu.status,
        winner_recipe_id=menu.winner_recipe_id,
        recipes=recipes,
        created_at=menu.created_at,
        user_voted_recipe_id=user_voted_recipe_id,
        total_votes=sum(vote_counts.values()),
    )


async def delete_menu(session: AsyncSession, menu: DailyMenu) -> None:
    await session.delete(menu)
    await session.commit()


async def recipe_exists(session: AsyncSession, recipe_id: uuid.UUID) -> bool:
    result = await session.execute(select(Recipe.id).where(Recipe.id == recipe_id))
    return result.scalar_one_or_none() is not None

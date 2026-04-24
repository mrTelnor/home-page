import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.menu import DailyMenu, DailyMenuRecipe
from app.db.models.recipe import Ingredient, Recipe


async def create_recipe(
    session: AsyncSession,
    title: str,
    description: str | None,
    servings: int,
    author_id: uuid.UUID,
    ingredients: list[dict],
    glyph_kind: str | None = None,
    glyph_color: str | None = None,
) -> Recipe:
    recipe = Recipe(
        id=uuid.uuid4(),
        title=title,
        description=description,
        servings=servings,
        author_id=author_id,
        glyph_kind=glyph_kind,
        glyph_color=glyph_color,
    )
    for ing in ingredients:
        recipe.ingredients.append(
            Ingredient(id=uuid.uuid4(), name=ing["name"], amount=ing["amount"], unit=ing.get("unit"))
        )
    session.add(recipe)
    await session.commit()
    await session.refresh(recipe, ["ingredients"])
    return recipe


async def get_all_recipes(session: AsyncSession) -> list[Recipe]:
    result = await session.execute(
        select(Recipe).options(selectinload(Recipe.ingredients)).order_by(Recipe.created_at.desc())
    )
    return list(result.scalars().all())


async def get_recipe_by_id(session: AsyncSession, recipe_id: uuid.UUID) -> Recipe | None:
    result = await session.execute(
        select(Recipe).where(Recipe.id == recipe_id).options(selectinload(Recipe.ingredients))
    )
    return result.scalar_one_or_none()


async def update_recipe(
    session: AsyncSession,
    recipe: Recipe,
    title: str | None,
    description: str | None,
    servings: int | None,
    ingredients: list[dict] | None,
    glyph_kind: str | None = None,
    glyph_color: str | None = None,
    glyph_provided: bool = False,
) -> Recipe:
    if title is not None:
        recipe.title = title
    if description is not None:
        recipe.description = description
    if servings is not None:
        recipe.servings = servings
    if glyph_provided:
        recipe.glyph_kind = glyph_kind
        recipe.glyph_color = glyph_color
    if ingredients is not None:
        recipe.ingredients.clear()
        for ing in ingredients:
            recipe.ingredients.append(
                Ingredient(id=uuid.uuid4(), name=ing["name"], amount=ing["amount"], unit=ing.get("unit"))
            )
    await session.commit()
    await session.refresh(recipe, ["ingredients", "updated_at"])
    return recipe


async def is_recipe_in_active_voting(session: AsyncSession, recipe_id: uuid.UUID) -> bool:
    result = await session.execute(
        select(DailyMenuRecipe)
        .join(DailyMenu, DailyMenuRecipe.menu_id == DailyMenu.id)
        .where(DailyMenuRecipe.recipe_id == recipe_id, DailyMenu.status == "voting")
    )
    return result.scalar_one_or_none() is not None


async def delete_recipe(session: AsyncSession, recipe: Recipe) -> None:
    await session.delete(recipe)
    await session.commit()


async def search_recipes(session: AsyncSession, query: str) -> list[Recipe]:
    result = await session.execute(
        select(Recipe)
        .where(Recipe.title.ilike(f"%{query}%"))
        .options(selectinload(Recipe.ingredients))
        .order_by(Recipe.title)
    )
    return list(result.scalars().all())

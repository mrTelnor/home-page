import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import NOT_ALLOWED, CurrentUser, DbSession
from app.schemas.recipe import RecipeCreateRequest, RecipeResponse, RecipeUpdateRequest
from app.services.recipe import (
    create_recipe,
    delete_recipe,
    get_all_recipes,
    get_recipe_by_id,
    is_recipe_in_active_voting,
    search_recipes,
    update_recipe,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])

RECIPE_NOT_FOUND = "Recipe not found"


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
async def create(data: RecipeCreateRequest, session: DbSession, user: CurrentUser):
    recipe = await create_recipe(
        session,
        title=data.title,
        description=data.description,
        servings=data.servings,
        author_id=user.id,
        ingredients=[ing.model_dump() for ing in data.ingredients],
        glyph_kind=data.glyph_kind,
        glyph_color=data.glyph_color,
    )
    return recipe


@router.get("", response_model=list[RecipeResponse])
async def list_all(session: DbSession):
    return await get_all_recipes(session)


@router.get("/search", response_model=list[RecipeResponse])
async def search(q: str, session: DbSession):
    return await search_recipes(session, q)


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_one(recipe_id: uuid.UUID, session: DbSession):
    recipe = await get_recipe_by_id(session, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=RECIPE_NOT_FOUND)
    return recipe


@router.put("/{recipe_id}", response_model=RecipeResponse)
async def update(
    recipe_id: uuid.UUID,
    data: RecipeUpdateRequest,
    session: DbSession,
    user: CurrentUser,
):
    recipe = await get_recipe_by_id(session, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=RECIPE_NOT_FOUND)
    if recipe.author_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_ALLOWED)

    fields_set = data.model_fields_set
    recipe = await update_recipe(
        session,
        recipe,
        title=data.title,
        description=data.description,
        servings=data.servings,
        ingredients=[ing.model_dump() for ing in data.ingredients] if data.ingredients is not None else None,
        glyph_kind=data.glyph_kind,
        glyph_color=data.glyph_color,
        glyph_provided="glyph_kind" in fields_set or "glyph_color" in fields_set,
    )
    return recipe


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(recipe_id: uuid.UUID, session: DbSession, user: CurrentUser):
    recipe = await get_recipe_by_id(session, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=RECIPE_NOT_FOUND)
    if recipe.author_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_ALLOWED)
    if await is_recipe_in_active_voting(session, recipe_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Recipe is in active voting")

    await delete_recipe(session, recipe)

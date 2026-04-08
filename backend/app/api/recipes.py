import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.recipe import RecipeCreateRequest, RecipeResponse, RecipeUpdateRequest
from app.services.recipe import (
    create_recipe,
    delete_recipe,
    get_all_recipes,
    get_recipe_by_id,
    is_recipe_in_active_voting,
    update_recipe,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
async def create(
    data: RecipeCreateRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = await create_recipe(
        session,
        title=data.title,
        description=data.description,
        servings=data.servings,
        author_id=user.id,
        ingredients=[ing.model_dump() for ing in data.ingredients],
    )
    return recipe


@router.get("", response_model=list[RecipeResponse])
async def list_all(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_all_recipes(session)


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_one(
    recipe_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = await get_recipe_by_id(session, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


@router.put("/{recipe_id}", response_model=RecipeResponse)
async def update(
    recipe_id: uuid.UUID,
    data: RecipeUpdateRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = await get_recipe_by_id(session, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    if recipe.author_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    recipe = await update_recipe(
        session,
        recipe,
        title=data.title,
        description=data.description,
        servings=data.servings,
        ingredients=[ing.model_dump() for ing in data.ingredients] if data.ingredients is not None else None,
    )
    return recipe


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    recipe_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = await get_recipe_by_id(session, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    if recipe.author_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if await is_recipe_in_active_voting(session, recipe_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Recipe is in active voting")

    await delete_recipe(session, recipe)

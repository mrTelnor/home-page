import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, verify_cron_or_admin
from app.db.models.user import User
from app.schemas.menu import (
    CreateDailyRequest,
    FinalizeDateRequest,
    MenuRecipeResponse,
    MenuResponse,
    SuggestRecipeRequest,
    VoteRequest,
)
from app.services.menu import (
    cancel_vote,
    cast_vote,
    close_voting,
    count_user_suggestions,
    create_daily_menu,
    delete_menu,
    finalize_menu,
    get_all_menus,
    get_menu_by_date,
    get_menu_by_id,
    get_user_vote,
    get_votes_for_menu,
    is_recipe_in_menu,
    recipe_exists,
    suggest_recipe,
)

router = APIRouter(prefix="/menus", tags=["menus"])


async def _build_menu_response(
    session: AsyncSession, menu, user_id: uuid.UUID | None = None
) -> MenuResponse:
    vote_counts = await get_votes_for_menu(session, menu.id) if menu.status != "collecting" else {}
    recipes = []
    for mr in menu.menu_recipes:
        from app.services.recipe import get_recipe_by_id

        recipe = await get_recipe_by_id(session, mr.recipe_id)
        recipes.append(
            MenuRecipeResponse(
                id=mr.id,
                recipe_id=mr.recipe_id,
                title=recipe.title if recipe else "Deleted recipe",
                source=mr.source,
                added_by=mr.added_by,
                votes_count=vote_counts.get(mr.recipe_id, 0),
            )
        )

    user_voted_recipe_id = None
    if user_id is not None and menu.status != "collecting":
        user_vote = await get_user_vote(session, menu.id, user_id)
        if user_vote:
            user_voted_recipe_id = user_vote.recipe_id

    total_votes = sum(vote_counts.values())

    return MenuResponse(
        id=menu.id,
        date=menu.date,
        status=menu.status,
        winner_recipe_id=menu.winner_recipe_id,
        recipes=recipes,
        created_at=menu.created_at,
        user_voted_recipe_id=user_voted_recipe_id,
        total_votes=total_votes,
    )


@router.post("/create-daily", response_model=MenuResponse, status_code=status.HTTP_201_CREATED)
async def create_daily(
    data: CreateDailyRequest,
    session: AsyncSession = Depends(get_db),
    _=Depends(verify_cron_or_admin),
):
    menu_date = data.date or date.today()
    existing = await get_menu_by_date(session, menu_date)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Menu for this date already exists")

    menu = await create_daily_menu(session, menu_date)
    return await _build_menu_response(session, menu)


@router.post("/{menu_id}/suggest", response_model=MenuResponse)
async def suggest(
    menu_id: uuid.UUID,
    data: SuggestRecipeRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    menu = await get_menu_by_id(session, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    if menu.status != "collecting":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Menu is not accepting suggestions")

    if not await recipe_exists(session, data.recipe_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    if await is_recipe_in_menu(session, menu.id, data.recipe_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Recipe already in menu")

    max_suggestions = 3 if user.role == "admin" else 1
    current = await count_user_suggestions(session, menu.id, user.id)
    if current >= max_suggestions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Suggestion limit reached")

    await suggest_recipe(session, menu, data.recipe_id, user.id)
    menu = await get_menu_by_id(session, menu.id)
    return await _build_menu_response(session, menu, user.id)


@router.post("/finalize", response_model=MenuResponse)
async def finalize(
    data: FinalizeDateRequest,
    session: AsyncSession = Depends(get_db),
    _=Depends(verify_cron_or_admin),
):
    menu_date = data.date or date.today()
    menu = await get_menu_by_date(session, menu_date)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    if menu.status in ("voting", "closed"):
        return await _build_menu_response(session, menu)

    menu = await finalize_menu(session, menu)
    return await _build_menu_response(session, menu)


@router.post("/close-voting", response_model=MenuResponse)
async def close(
    data: FinalizeDateRequest,
    session: AsyncSession = Depends(get_db),
    _=Depends(verify_cron_or_admin),
):
    menu_date = data.date or date.today()
    menu = await get_menu_by_date(session, menu_date)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    if menu.status == "closed":
        return await _build_menu_response(session, menu)
    if menu.status != "voting":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Menu is not in voting status")

    menu = await close_voting(session, menu)
    return await _build_menu_response(session, menu)


@router.post("/{menu_id}/vote", response_model=MenuResponse)
async def vote(
    menu_id: uuid.UUID,
    data: VoteRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    menu = await get_menu_by_id(session, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    if menu.status != "voting":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voting is not open")

    if not await is_recipe_in_menu(session, menu.id, data.recipe_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recipe is not in this menu")

    try:
        await cast_vote(session, menu.id, data.recipe_id, user.id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already voted for this menu")

    menu = await get_menu_by_id(session, menu.id)
    return await _build_menu_response(session, menu, user.id)


@router.delete("/{menu_id}/vote", response_model=MenuResponse)
async def cancel_user_vote(
    menu_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    menu = await get_menu_by_id(session, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    if menu.status != "voting":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Voting is not open")

    await cancel_vote(session, menu.id, user.id)
    menu = await get_menu_by_id(session, menu.id)
    return await _build_menu_response(session, menu, user.id)


@router.get("/today", response_model=MenuResponse)
async def today(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    menu = await get_menu_by_date(session, date.today())
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No menu for today")
    return await _build_menu_response(session, menu, user.id)


@router.get("", response_model=list[MenuResponse])
async def list_all(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    menus = await get_all_menus(session)
    return [await _build_menu_response(session, m, user.id) for m in menus]


@router.get("/{menu_id}", response_model=MenuResponse)
async def get_one(
    menu_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    menu = await get_menu_by_id(session, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    return await _build_menu_response(session, menu, user.id)


@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    menu_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    menu = await get_menu_by_id(session, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    await delete_menu(session, menu)

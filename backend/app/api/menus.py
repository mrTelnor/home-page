import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import NOT_ALLOWED, CronOrAdmin, CurrentUser, DbSession
from app.schemas.menu import (
    CreateDailyRequest,
    FinalizeDateRequest,
    MenuResponse,
    SuggestRecipeRequest,
    VoteRequest,
)
from app.services.menu import (
    build_menu_response,
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
    is_recipe_in_menu,
    recipe_exists,
    suggest_recipe,
)

router = APIRouter(prefix="/menus", tags=["menus"])

MENU_NOT_FOUND = "Menu not found"
VOTING_NOT_OPEN = "Voting is not open"


@router.post("/create-daily", response_model=MenuResponse, status_code=status.HTTP_201_CREATED)
async def create_daily(data: CreateDailyRequest, session: DbSession, _: CronOrAdmin):
    menu_date = data.date or date.today()
    existing = await get_menu_by_date(session, menu_date)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Menu for this date already exists")

    menu = await create_daily_menu(session, menu_date)
    return await build_menu_response(session, menu)


@router.post("/{menu_id}/suggest", response_model=MenuResponse)
async def suggest(
    menu_id: uuid.UUID,
    data: SuggestRecipeRequest,
    session: DbSession,
    user: CurrentUser,
):
    menu = await get_menu_by_id(session, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MENU_NOT_FOUND)
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
    return await build_menu_response(session, menu, user.id)


@router.post("/finalize", response_model=MenuResponse)
async def finalize(data: FinalizeDateRequest, session: DbSession, _: CronOrAdmin):
    menu_date = data.date or date.today()
    menu = await get_menu_by_date(session, menu_date)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MENU_NOT_FOUND)
    if menu.status in ("voting", "closed"):
        return await build_menu_response(session, menu)

    menu = await finalize_menu(session, menu)
    return await build_menu_response(session, menu)


@router.post("/close-voting", response_model=MenuResponse)
async def close(data: FinalizeDateRequest, session: DbSession, _: CronOrAdmin):
    menu_date = data.date or date.today()
    menu = await get_menu_by_date(session, menu_date)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MENU_NOT_FOUND)
    if menu.status == "closed":
        return await build_menu_response(session, menu)
    if menu.status != "voting":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Menu is not in voting status")

    menu = await close_voting(session, menu)
    return await build_menu_response(session, menu)


@router.post("/{menu_id}/vote", response_model=MenuResponse)
async def vote(
    menu_id: uuid.UUID,
    data: VoteRequest,
    session: DbSession,
    user: CurrentUser,
):
    menu = await get_menu_by_id(session, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MENU_NOT_FOUND)
    if menu.status != "voting":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=VOTING_NOT_OPEN)

    if not await is_recipe_in_menu(session, menu.id, data.recipe_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recipe is not in this menu")

    try:
        await cast_vote(session, menu.id, data.recipe_id, user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already voted for this menu"
        ) from exc

    menu = await get_menu_by_id(session, menu.id)
    return await build_menu_response(session, menu, user.id)


@router.delete("/{menu_id}/vote", response_model=MenuResponse)
async def cancel_user_vote(menu_id: uuid.UUID, session: DbSession, user: CurrentUser):
    menu = await get_menu_by_id(session, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MENU_NOT_FOUND)
    if menu.status != "voting":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=VOTING_NOT_OPEN)

    await cancel_vote(session, menu.id, user.id)
    menu = await get_menu_by_id(session, menu.id)
    return await build_menu_response(session, menu, user.id)


@router.get("/today", response_model=MenuResponse)
async def today(session: DbSession, user: CurrentUser):
    menu = await get_menu_by_date(session, date.today())
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No menu for today")
    return await build_menu_response(session, menu, user.id)


@router.get("", response_model=list[MenuResponse])
async def list_all(session: DbSession, user: CurrentUser):
    menus = await get_all_menus(session)
    return [await build_menu_response(session, m, user.id) for m in menus]


@router.get("/{menu_id}", response_model=MenuResponse)
async def get_one(menu_id: uuid.UUID, session: DbSession, user: CurrentUser):
    menu = await get_menu_by_id(session, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MENU_NOT_FOUND)
    return await build_menu_response(session, menu, user.id)


@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(menu_id: uuid.UUID, session: DbSession, user: CurrentUser):
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_ALLOWED)
    menu = await get_menu_by_id(session, menu_id)
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MENU_NOT_FOUND)
    await delete_menu(session, menu)

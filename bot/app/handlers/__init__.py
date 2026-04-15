from aiogram import Router

from app.handlers.menu import router as menu_router
from app.handlers.notifications import router as notifications_router
from app.handlers.recipes import router as recipes_router
from app.handlers.start import router as start_router
from app.handlers.suggest import router as suggest_router
from app.handlers.vote import router as vote_router

main_router = Router()
main_router.include_router(start_router)
main_router.include_router(menu_router)
main_router.include_router(vote_router)
main_router.include_router(suggest_router)
main_router.include_router(recipes_router)
main_router.include_router(notifications_router)

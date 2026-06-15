import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.menus import router as menus_router
from app.api.recipes import router as recipes_router
from app.core.config import settings
from app.core.db import dispose_engine

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Home Page API started")
    yield
    await dispose_engine()


app = FastAPI(title="Home Page API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or [f"https://{settings.domain}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.recipe_images_dir, exist_ok=True)
app.mount(
    "/api/recipe-images",
    StaticFiles(directory=settings.recipe_images_dir),
    name="recipe-images",
)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(recipes_router, prefix="/api")
app.include_router(menus_router, prefix="/api")

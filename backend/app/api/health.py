import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import async_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health():
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except (SQLAlchemyError, OSError):
        # Детали (DSN/хост/юзер/имя БД) — только в лог; наружу эндпоинт публичный
        logger.exception("Health check failed")
        return JSONResponse(status_code=503, content={"status": "error"})

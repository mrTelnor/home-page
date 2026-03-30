from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import async_session

router = APIRouter()


@router.get("/health")
async def health():
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": str(e)},
        )

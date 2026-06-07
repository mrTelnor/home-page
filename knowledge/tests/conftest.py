import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_URL = os.environ.get(
    "KNOWLEDGE_TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge_test",
)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_URL)
    SessionMaker = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionMaker() as session:
        yield session
    await engine.dispose()

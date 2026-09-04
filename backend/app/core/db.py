from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

# pool_pre_ping: проверять соединение перед использованием — после рестарта
# Postgres/разрыва NAT «мёртвые» соединения из пула иначе роняют первые запросы.
# pool_recycle: пересоздавать соединения старше 30 мин (тот же класс проблем).
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def dispose_engine() -> None:
    await engine.dispose()

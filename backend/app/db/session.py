from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

Fabrica = async_sessionmaker[AsyncSession]


def criar_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        hide_parameters=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )


def criar_fabrica(engine: AsyncEngine) -> Fabrica:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

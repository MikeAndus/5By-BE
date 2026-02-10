from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url

    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)

    return url


settings = get_settings()
_database_url = normalize_database_url(settings.database_url) if settings.database_url else None

engine: AsyncEngine | None = (
    create_async_engine(
        _database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
    )
    if _database_url
    else None
)

async_session_factory: async_sessionmaker[AsyncSession] | None = (
    async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    if engine is not None
    else None
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        raise RuntimeError("Database is not configured")

    async with async_session_factory() as session:
        yield session

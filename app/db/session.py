from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


def normalize_async_database_url(url: str) -> str:
    # Decision: accept Render-style `postgres://` input and normalize to asyncpg.
    normalized = url.strip()

    if normalized.startswith("postgres://"):
        normalized = normalized.replace("postgres://", "postgresql://", 1)

    if normalized.startswith("postgresql+asyncpg://"):
        return normalized

    if normalized.startswith("postgresql+"):
        _, rest = normalized.split("://", 1)
        return f"postgresql+asyncpg://{rest}"

    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+asyncpg://", 1)

    raise ValueError(
        "DATABASE_URL must start with postgres://, postgresql://, or postgresql+<driver>://"
    )


def normalize_sync_database_url(url: str) -> str:
    # Decision: keep Alembic on sync psycopg for predictable migration operations.
    normalized = url.strip()

    if normalized.startswith("postgres://"):
        normalized = normalized.replace("postgres://", "postgresql://", 1)

    if normalized.startswith("postgresql+psycopg://"):
        return normalized

    if normalized.startswith("postgresql+"):
        _, rest = normalized.split("://", 1)
        return f"postgresql+psycopg://{rest}"

    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+psycopg://", 1)

    raise ValueError(
        "DATABASE_URL must start with postgres://, postgresql://, or postgresql+<driver>://"
    )


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        normalize_async_database_url(settings.database_url),
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_async_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=get_async_engine(), class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        yield session


async def db_ping(session: AsyncSession) -> bool:
    await session.execute(text("SELECT 1"))
    return True


__all__ = [
    "db_ping",
    "get_async_engine",
    "get_async_session",
    "get_async_sessionmaker",
    "normalize_async_database_url",
    "normalize_sync_database_url",
]

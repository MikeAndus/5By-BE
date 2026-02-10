from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.constants import SERVICE_NAME
from app.core.errors import HealthDb, HealthResponse
from app.db.session import normalize_database_url

router = APIRouter()

DB_UNAVAILABLE_DETAIL = {
    "code": "db_unavailable",
    "message": "Database is not reachable",
}


async def _check_database_connectivity(database_url: str) -> None:
    engine = create_async_engine(
        normalize_database_url(database_url),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=1,
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    settings = get_settings()

    if not settings.database_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DB_UNAVAILABLE_DETAIL,
        )

    try:
        await _check_database_connectivity(settings.database_url)
    except (SQLAlchemyError, ValueError, OSError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=DB_UNAVAILABLE_DETAIL,
        ) from None

    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        db=HealthDb(status="ok"),
        cors_debug=settings.cors_allowed_origins,
    )

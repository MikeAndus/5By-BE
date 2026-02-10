from __future__ import annotations

import time
from asyncio import TimeoutError as AsyncTimeoutError
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import db_ping, get_async_session

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["health"])
APP_VERSION = "0.1.0"


class HealthDbStatus(BaseModel):
    checked: bool
    ok: bool | None
    error: Literal["database_unreachable", "database_timeout", "database_error"] | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    env: str
    version: str
    uptime_s: float
    db: HealthDbStatus


def _db_error_code(exc: Exception) -> str:
    if isinstance(exc, AsyncTimeoutError):
        return "database_timeout"
    if isinstance(exc, OperationalError):
        return "database_unreachable"
    if isinstance(exc, SQLAlchemyError):
        return "database_error"
    return "database_error"


@router.get("/health", response_model=HealthResponse)
async def health_check(
    request: Request,
    db: bool = Query(False, description="When true, perform a database connectivity check."),
    session: AsyncSession = Depends(get_async_session),
) -> HealthResponse | JSONResponse:
    settings = get_settings()
    process_started_at = getattr(request.app.state, "process_started_at", time.monotonic())
    uptime_s = round(time.monotonic() - process_started_at, 2)

    payload = {
        "status": "ok",
        "service": settings.service_name,
        "env": settings.env,
        "version": APP_VERSION,
        "uptime_s": uptime_s,
        "db": {"checked": db, "ok": True if db else None},
    }

    if not db:
        return HealthResponse.model_validate(payload)

    try:
        await db_ping(session)
        payload["db"] = {"checked": True, "ok": True}
        return HealthResponse.model_validate(payload)
    except Exception as exc:
        error_code = _db_error_code(exc)
        logger.warning("health_db_ping_failed", error=error_code)
        payload["status"] = "degraded"
        payload["db"] = {"checked": True, "ok": False, "error": error_code}
        return JSONResponse(status_code=503, content=payload)

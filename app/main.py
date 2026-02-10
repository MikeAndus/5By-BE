import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import health, sessions
from app.core.config import get_settings
from app.core.errors import ApiError, ApiErrorResponse

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | list[Any] | str | None = None,
) -> JSONResponse:
    payload = ApiErrorResponse(
        error=ApiError(code=code, message=message, details=details),
    ).model_dump(exclude_none=True)
    return JSONResponse(status_code=status_code, content=payload)


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(title="five-by-backend")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="validation_error",
            message="Request validation failed",
            details=exc.errors(),
        )

    @application.exception_handler(HTTPException)
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException | StarletteHTTPException,
    ) -> JSONResponse:
        details: dict[str, Any] | list[Any] | str | None = None

        if isinstance(exc.detail, dict):
            code = str(exc.detail.get("code", "http_error"))
            message = str(exc.detail.get("message", exc.detail.get("detail", "HTTP error")))
            details = exc.detail.get("details")
        elif isinstance(exc.detail, str):
            code = "http_error"
            message = exc.detail
        else:
            code = "http_error"
            message = "HTTP error"
            details = exc.detail

        return _error_response(
            status_code=exc.status_code,
            code=code,
            message=message,
            details=details,
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", exc_info=exc)
        return _error_response(
            status_code=500,
            code="internal_error",
            message="Unexpected server error",
        )

    application.include_router(health.router)
    application.include_router(sessions.router)
    return application


app = create_app()

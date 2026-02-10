from __future__ import annotations

import os
import time

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import ApiErrorCode, ApiException, make_error_payload
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

logger = structlog.get_logger(__name__)


def _request_id_from_request(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) and request_id else "unknown"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = _request_id_from_request(request)
        details = exc.errors()
        logger.warning(
            "request_validation_error",
            method=request.method,
            path=request.url.path,
            details=details,
        )
        return JSONResponse(
            status_code=422,
            headers={"X-Request-ID": request_id},
            content={
                **make_error_payload(
                    code=ApiErrorCode.VALIDATION_ERROR,
                    message="Invalid request",
                    details=details,
                ),
                "request_id": request_id,
            },
        )

    @app.exception_handler(ApiException)
    async def api_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
        request_id = _request_id_from_request(request)
        logger.warning(
            "api_exception",
            method=request.method,
            path=request.url.path,
            status_code=exc.status_code,
            code=exc.code,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            headers={"X-Request-ID": request_id},
            content={
                **make_error_payload(
                    code=exc.code,
                    message=exc.message,
                    details=exc.details,
                ),
                "request_id": request_id,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = _request_id_from_request(request)
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        logger.warning(
            "http_exception",
            method=request.method,
            path=request.url.path,
            status_code=exc.status_code,
            detail=message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            headers={"X-Request-ID": request_id},
            content={
                **make_error_payload(code=ApiErrorCode.HTTP_ERROR, message=message, details=[]),
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id_from_request(request)
        logger.exception(
            "unhandled_exception",
            method=request.method,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": request_id},
            content={
                **make_error_payload(
                    code=ApiErrorCode.INTERNAL_ERROR,
                    message="Internal server error",
                    details=[],
                ),
                "request_id": request_id,
            },
        )


def create_app() -> FastAPI:
    initial_log_level = os.getenv("LOG_LEVEL", "INFO")
    configure_logging(initial_log_level)
    settings = get_settings()
    if settings.log_level.upper() != initial_log_level.upper():
        configure_logging(settings.log_level)

    app = FastAPI(title="Five-By Backend", version="0.1.0")
    app.state.process_started_at = time.monotonic()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router)

    logger.info("app_initialized", service=settings.service_name, env=settings.env)
    return app


app = create_app()

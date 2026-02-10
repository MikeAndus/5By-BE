from typing import Any

from pydantic import BaseModel


class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | list[Any] | str | None = None


class ApiErrorResponse(BaseModel):
    error: ApiError


class HealthDb(BaseModel):
    status: str


class HealthResponse(BaseModel):
    status: str
    service: str
    db: HealthDb

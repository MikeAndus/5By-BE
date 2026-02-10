from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ApiErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_NOT_IN_PROGRESS = "SESSION_NOT_IN_PROGRESS"
    OUT_OF_TURN = "OUT_OF_TURN"
    STATE_CORRUPT = "STATE_CORRUPT"
    CELL_ALREADY_REVEALED = "CELL_ALREADY_REVEALED"
    CELL_LOCKED = "CELL_LOCKED"
    TOPIC_ALREADY_USED = "TOPIC_ALREADY_USED"
    TOPIC_LIMIT_REACHED = "TOPIC_LIMIT_REACHED"
    MUTATION_NOT_IMPLEMENTED = "MUTATION_NOT_IMPLEMENTED"


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = Field(default=None)


class ApiError(BaseModel):
    error: ApiErrorDetail


DEFAULT_MESSAGES: dict[str, str] = {
    ApiErrorCode.VALIDATION_ERROR.value: "Invalid request",
    ApiErrorCode.HTTP_ERROR.value: "Request failed",
    ApiErrorCode.INTERNAL_ERROR.value: "Internal server error",
    ApiErrorCode.SESSION_NOT_FOUND.value: "Session not found",
    ApiErrorCode.SESSION_NOT_IN_PROGRESS.value: "Session is not in progress",
    ApiErrorCode.OUT_OF_TURN.value: "Player is acting out of turn",
    ApiErrorCode.STATE_CORRUPT.value: "Session state is inconsistent",
    ApiErrorCode.CELL_ALREADY_REVEALED.value: "Cell is already revealed",
    ApiErrorCode.CELL_LOCKED.value: "Cell is locked",
    ApiErrorCode.TOPIC_ALREADY_USED.value: "Topic has already been used for this cell",
    ApiErrorCode.TOPIC_LIMIT_REACHED.value: "Topic limit reached for this cell",
    ApiErrorCode.MUTATION_NOT_IMPLEMENTED.value: "Mutation logic not implemented yet",
}


class ApiException(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: ApiErrorCode | str,
        message: str | None = None,
        details: Any | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code.value if isinstance(code, ApiErrorCode) else code
        self.message = message or DEFAULT_MESSAGES.get(self.code, "Request failed")
        self.details = details
        super().__init__(self.message)


class NotFoundError(ApiException):
    def __init__(self, code: ApiErrorCode | str, message: str | None = None, details: Any | None = None) -> None:
        super().__init__(status_code=404, code=code, message=message, details=details)


class RuleViolationError(ApiException):
    def __init__(self, code: ApiErrorCode | str, message: str | None = None, details: Any | None = None) -> None:
        super().__init__(status_code=409, code=code, message=message, details=details)


def make_error_payload(code: ApiErrorCode | str, message: str, details: Any | None = None) -> dict[str, Any]:
    code_value = code.value if isinstance(code, ApiErrorCode) else code
    payload = ApiError(
        error=ApiErrorDetail(
            code=code_value,
            message=message,
            details=details,
        )
    ).model_dump(exclude_none=True)
    return payload


__all__ = [
    "ApiError",
    "ApiErrorCode",
    "ApiException",
    "NotFoundError",
    "RuleViolationError",
    "make_error_payload",
]

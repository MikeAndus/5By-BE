from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RateLimitStubMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # TODO: add real rate-limiting for LLM-heavy endpoints (for example /sessions/{id}/ask).
        return await call_next(request)

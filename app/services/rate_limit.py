from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from math import ceil
import time
import uuid

from fastapi import HTTPException, status

from app.core.config import get_settings


_ask_rate_limit_buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_ask_rate_limit_lock = asyncio.Lock()


def _build_rate_limit_key(*, session_id: uuid.UUID, client_ip: str | None) -> tuple[str, str]:
    return (str(session_id), client_ip or "unknown")


async def enforce_ask_rate_limit(*, session_id: uuid.UUID, client_ip: str | None) -> None:
    settings = get_settings()
    limit = settings.ask_rate_limit_requests
    window_seconds = settings.ask_rate_limit_window_seconds

    async with _ask_rate_limit_lock:
        now = time.monotonic()
        window_start = now - float(window_seconds)
        key = _build_rate_limit_key(session_id=session_id, client_ip=client_ip)
        bucket = _ask_rate_limit_buckets[key]

        while bucket and bucket[0] <= window_start:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after_seconds = max(1, ceil(bucket[0] + float(window_seconds) - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "rate_limited",
                    "message": "Too many requests",
                    "details": {"retry_after_seconds": retry_after_seconds},
                },
            )

        bucket.append(now)

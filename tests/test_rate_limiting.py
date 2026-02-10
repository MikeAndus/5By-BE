from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.services import rate_limit


@pytest.mark.asyncio
async def test_exceed_ask_rate_limit_returns_429() -> None:
    rate_limit._ask_rate_limit_buckets.clear()
    session_id = uuid.uuid4()

    for _ in range(10):
        await rate_limit.enforce_ask_rate_limit(session_id=session_id, client_ip="127.0.0.1")

    with pytest.raises(HTTPException) as exc_info:
        await rate_limit.enforce_ask_rate_limit(session_id=session_id, client_ip="127.0.0.1")

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["code"] == "rate_limited"
    assert exc_info.value.detail["message"] == "Too many requests"

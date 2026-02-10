from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import get_settings


class OpenAIClientUnavailableError(RuntimeError):
    pass


@lru_cache
def _build_client(api_key: str) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key)


def get_openai_client() -> AsyncOpenAI:
    api_key = (get_settings().openai_api_key or "").strip()
    if not api_key:
        raise OpenAIClientUnavailableError("OPENAI_API_KEY is not configured")

    return _build_client(api_key)

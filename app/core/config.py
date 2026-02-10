from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Decision: use Pydantic Settings v2 with optional `.env` loading for local dev.
    # Production/staging should inject real environment variables at runtime.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env: Literal["local", "staging", "production"] = "local"
    service_name: str = "five-by-backend"
    log_level: str = "INFO"
    database_url: str
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    openai_api_key: str | None = None

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_allow_origins(cls, value: object) -> list[str]:
        if value is None:
            return ["http://localhost:5173"]

        if isinstance(value, str):
            origins = [origin.strip() for origin in value.split(",")]
            return [origin for origin in origins if origin]

        if isinstance(value, list):
            origins = [str(origin).strip() for origin in value]
            return [origin for origin in origins if origin]

        raise ValueError("CORS_ALLOW_ORIGINS must be a comma-separated string or list")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

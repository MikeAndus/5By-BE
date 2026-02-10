from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    trivia_generator_mode: str = Field(default="stub", alias="TRIVIA_GENERATOR_MODE")
    ask_rate_limit_requests: int = Field(default=10, alias="ASK_RATE_LIMIT_REQUESTS")
    ask_rate_limit_window_seconds: int = Field(default=60, alias="ASK_RATE_LIMIT_WINDOW_SECONDS")
    cors_allowed_origins: str | list[str] = Field(
        default_factory=lambda: DEFAULT_CORS_ALLOWED_ORIGINS.copy(),
        alias="CORS_ALLOWED_ORIGINS",
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: Any) -> list[str]:
        if value is None:
            return DEFAULT_CORS_ALLOWED_ORIGINS.copy()

        if isinstance(value, str):
            parsed = [origin.strip() for origin in value.split(",") if origin.strip()]
            return parsed or DEFAULT_CORS_ALLOWED_ORIGINS.copy()

        if isinstance(value, list):
            parsed = [str(origin).strip() for origin in value if str(origin).strip()]
            return parsed or DEFAULT_CORS_ALLOWED_ORIGINS.copy()

        return DEFAULT_CORS_ALLOWED_ORIGINS.copy()

    @field_validator("trivia_generator_mode")
    @classmethod
    def validate_trivia_generator_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"stub", "openai"}:
            raise ValueError("TRIVIA_GENERATOR_MODE must be one of: stub, openai")
        return normalized

    @field_validator("ask_rate_limit_requests", "ask_rate_limit_window_seconds")
    @classmethod
    def validate_positive_rate_limit_values(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Rate limit values must be > 0")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

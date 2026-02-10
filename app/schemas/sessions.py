from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_1_name: str | None = Field(default=None, max_length=30)
    player_2_name: str | None = Field(default=None, max_length=30)

    @field_validator("player_1_name", "player_2_name", mode="before")
    @classmethod
    def normalize_player_name(cls, value: object) -> object:
        if value is None:
            return None

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        return value


__all__ = ["CreateSessionRequest"]

from pydantic import BaseModel, ConfigDict, field_validator


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_1_name: str | None = None
    player_2_name: str | None = None

    @field_validator("player_1_name", "player_2_name")
    @classmethod
    def validate_player_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        trimmed = value.strip()
        if len(trimmed) == 0:
            raise ValueError("name cannot be empty")
        if len(trimmed) > 30:
            raise ValueError("name must be at most 30 characters")
        return trimmed

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import CANONICAL_TOPICS
from app.schemas.enums import EventType, RevealedBy, SessionStatus, Topic


class CellSnapshot(BaseModel):
    index: int = Field(ge=0, le=24)
    row: int = Field(ge=0, le=4)
    col: int = Field(ge=0, le=4)
    revealed: bool
    locked: bool
    letter: str | None = Field(default=None, min_length=1, max_length=1, pattern="^[A-Z]$")
    revealed_by: RevealedBy | None = None
    topics_used: list[Topic]

    @field_validator("topics_used")
    @classmethod
    def validate_topics_used(cls, value: list[Topic]) -> list[Topic]:
        if len(value) > 5:
            raise ValueError("topics_used must have length <= 5")
        return value

    @model_validator(mode="after")
    def validate_revealed_consistency(self) -> "CellSnapshot":
        if not self.revealed:
            if self.letter is not None:
                raise ValueError("letter must be null when revealed is false")
            if self.revealed_by is not None:
                raise ValueError("revealed_by must be null when revealed is false")
            return self

        if self.letter is None:
            raise ValueError("letter must be set when revealed is true")
        return self


class PlayerSnapshot(BaseModel):
    player_number: Literal[1, 2]
    name: str | None = Field(default=None, max_length=30)
    score: int
    grid_id: int
    completed: bool
    cells: list[CellSnapshot]


class LastEvent(BaseModel):
    type: EventType
    event_data: dict[str, Any]
    created_at: datetime


class SessionSnapshot(BaseModel):
    session_id: uuid.UUID
    status: SessionStatus
    current_turn: Literal[1, 2]
    topics: list[Topic]
    players: list[PlayerSnapshot] = Field(min_length=2, max_length=2)
    last_event: LastEvent | None
    created_at: datetime
    updated_at: datetime

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, value: list[Topic]) -> list[Topic]:
        expected = [Topic(topic) for topic in CANONICAL_TOPICS]
        if value != expected:
            raise ValueError("topics must match CANONICAL_TOPICS in canonical order")
        return value

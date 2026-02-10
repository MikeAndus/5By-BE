from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field, field_validator

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
    topics: list[Topic]

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, value: list[Topic]) -> list[Topic]:
        expected = [Topic(topic) for topic in CANONICAL_TOPICS]
        if value != expected:
            raise ValueError("topics must match CANONICAL_TOPICS in canonical order")
        return value


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
    players: list[PlayerSnapshot] = Field(min_length=2, max_length=2)
    last_event: LastEvent | None
    created_at: datetime
    updated_at: datetime

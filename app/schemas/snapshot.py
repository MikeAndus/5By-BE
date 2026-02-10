from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, model_serializer


class SnapshotLastEvent(BaseModel):
    type: str
    result: str | None = None
    message_to_speak: str | None = None

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        payload = handler(self)
        if payload.get("result") is None:
            payload.pop("result", None)
        if payload.get("message_to_speak") is None:
            payload.pop("message_to_speak", None)
        return payload


class SessionCellSnapshot(BaseModel):
    index: int = Field(ge=0, le=24)
    row: int = Field(ge=0, le=4)
    col: int = Field(ge=0, le=4)
    revealed: bool
    letter: str | None = None
    locked: bool
    topics_used: list[str]
    revealed_by: Literal["question", "guess", "auto"] | None = None

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        payload = handler(self)
        if payload.get("letter") is None:
            payload.pop("letter", None)
        return payload


class SessionPlayerSnapshot(BaseModel):
    player_number: Literal[1, 2]
    name: str | None = None
    score: int
    grid_id: UUID
    cells: list[SessionCellSnapshot] = Field(min_length=25, max_length=25)
    completed: bool


class SessionSnapshot(BaseModel):
    session_id: UUID
    status: Literal["lobby", "in_progress", "complete"]
    current_turn: Literal[1, 2]
    players: list[SessionPlayerSnapshot] = Field(min_length=2, max_length=2)
    last_event: SnapshotLastEvent


__all__ = [
    "SessionCellSnapshot",
    "SessionPlayerSnapshot",
    "SessionSnapshot",
    "SnapshotLastEvent",
]

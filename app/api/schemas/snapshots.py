from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.schemas.enums import RevealedBy, SessionStatus, TOPIC_VALUES
from app.api.utils.grid import cell_index_from_row_col

_SINGLE_LETTER_RE = re.compile(r"^[A-Z]$")


class CellSnapshot(BaseModel):
    index: int = Field(ge=0, le=24)
    row: int = Field(ge=0, le=4)
    col: int = Field(ge=0, le=4)
    revealed: bool
    letter: str | None = None
    locked: bool
    topics_used: list[str] = Field(default_factory=list)
    revealed_by: RevealedBy | None = None

    @field_validator("topics_used")
    @classmethod
    def validate_topics_used(cls, value: list[str]) -> list[str]:
        invalid_topics = sorted(set(value).difference(TOPIC_VALUES))
        if invalid_topics:
            raise ValueError(f"topics_used has unsupported topics: {invalid_topics}")
        return value

    @model_validator(mode="after")
    def validate_coordinates_and_letter(self) -> "CellSnapshot":
        expected_index = cell_index_from_row_col(self.row, self.col)
        if expected_index != self.index:
            raise ValueError("index does not match row/col")

        if not self.revealed:
            if self.letter is not None:
                raise ValueError("letter must be null when revealed is false")
            return self

        if self.letter is None:
            return self

        if not _SINGLE_LETTER_RE.fullmatch(self.letter):
            raise ValueError("letter must be a single uppercase A-Z character")

        return self


class PlayerSnapshot(BaseModel):
    player_number: Literal[1, 2]
    name: str | None = None
    score: int
    grid_id: UUID
    cells: list[CellSnapshot] = Field(min_length=25, max_length=25)
    completed: bool

    @model_validator(mode="after")
    def validate_cells_cover_grid(self) -> "PlayerSnapshot":
        indexes = sorted(cell.index for cell in self.cells)
        if indexes != list(range(25)):
            raise ValueError("cells must contain each grid index exactly once (0..24)")
        return self


class LastEventSnapshot(BaseModel):
    type: str
    result: Literal["ok", "error"] | None = None
    message_to_speak: str | None = None


class SessionSnapshot(BaseModel):
    session_id: UUID
    status: SessionStatus
    current_turn: Literal[1, 2]
    players: list[PlayerSnapshot] = Field(min_length=2, max_length=2)
    last_event: LastEventSnapshot | None = None

    @model_validator(mode="after")
    def validate_players(self) -> "SessionSnapshot":
        player_numbers = sorted(player.player_number for player in self.players)
        if player_numbers != [1, 2]:
            raise ValueError("players must contain exactly player 1 and player 2")
        return self


__all__ = [
    "CellSnapshot",
    "LastEventSnapshot",
    "PlayerSnapshot",
    "SessionSnapshot",
]

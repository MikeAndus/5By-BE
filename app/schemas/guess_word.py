from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.enums import GuessDirection

FiveLetterWord = Annotated[str, StringConstraints(pattern="^[A-Za-z]{5}$")]
UpperFiveLetterWord = Annotated[str, StringConstraints(pattern="^[A-Z]{5}$")]
CellIndex = Annotated[int, Field(ge=0, le=24)]


class GuessWordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_number: Literal[1, 2]
    direction: GuessDirection
    index: int = Field(ge=0, le=4)
    word: FiveLetterWord


class RevealedCellEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_index: CellIndex
    row: int = Field(ge=0, le=4)
    col: int = Field(ge=0, le=4)
    revealed_letter: Annotated[str, StringConstraints(pattern="^[A-Z]$")]

    @model_validator(mode="after")
    def validate_coordinates(self) -> "RevealedCellEvent":
        if self.row != self.cell_index // 5:
            raise ValueError("row must equal cell_index // 5")
        if self.col != self.cell_index % 5:
            raise ValueError("col must equal cell_index % 5")
        return self


class WordGuessedEventData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: GuessDirection
    index: int = Field(ge=0, le=4)
    guessed_word: UpperFiveLetterWord
    correct: bool
    revealed_cells: list[RevealedCellEvent] = Field(default_factory=list)
    score_delta: int
    opponent_score_delta: int
    locks_enqueued: list[CellIndex] = Field(default_factory=list)
    auto_reveals: list[RevealedCellEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payload(self) -> "WordGuessedEventData":
        revealed_indices = [cell.cell_index for cell in self.revealed_cells]
        if revealed_indices != sorted(revealed_indices):
            raise ValueError("revealed_cells must be sorted by ascending cell_index")

        if self.locks_enqueued != sorted(self.locks_enqueued):
            raise ValueError("locks_enqueued must be sorted ascending")

        if self.correct:
            if self.score_delta != 0 or self.opponent_score_delta != 0:
                raise ValueError("score deltas must be zero when correct is true")
            if self.locks_enqueued:
                raise ValueError("locks_enqueued must be empty when correct is true")
            return self

        if self.score_delta != -5 or self.opponent_score_delta != 1:
            raise ValueError("score deltas must be -5/+1 when correct is false")
        if self.revealed_cells:
            raise ValueError("revealed_cells must be empty when correct is false")
        if self.auto_reveals:
            raise ValueError("auto_reveals must be empty when correct is false")
        return self

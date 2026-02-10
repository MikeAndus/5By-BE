from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SingleLetter = Annotated[str, StringConstraints(pattern="^[A-Za-z]$")]
UpperSingleLetter = Annotated[str, StringConstraints(pattern="^[A-Z]$")]


class GuessLetterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_number: Literal[1, 2]
    cell_index: int = Field(ge=0, le=24)
    letter: SingleLetter


class RevealedCellEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_index: int = Field(ge=0, le=24)
    row: int = Field(ge=0, le=4)
    col: int = Field(ge=0, le=4)
    revealed_letter: UpperSingleLetter


class LetterGuessedEventData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_index: int = Field(ge=0, le=24)
    row: int = Field(ge=0, le=4)
    col: int = Field(ge=0, le=4)
    guessed_letter: UpperSingleLetter
    correct: bool
    revealed_letter: UpperSingleLetter | None = None
    score_delta: int
    opponent_score_delta: int
    locks_enqueued: list[int] = Field(default_factory=list)
    auto_reveals: list[RevealedCellEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payload(self) -> "LetterGuessedEventData":
        if self.row != self.cell_index // 5:
            raise ValueError("row must equal cell_index // 5")
        if self.col != self.cell_index % 5:
            raise ValueError("col must equal cell_index % 5")
        if any(lock < 0 or lock > 24 for lock in self.locks_enqueued):
            raise ValueError("locks_enqueued indices must be in range 0..24")

        if self.correct:
            if self.revealed_letter is None:
                raise ValueError("revealed_letter must be present when correct is true")
            if self.score_delta != 0 or self.opponent_score_delta != 0:
                raise ValueError("score deltas must be zero when correct is true")
            if self.locks_enqueued:
                raise ValueError("locks_enqueued must be empty when correct is true")
            return self

        if self.revealed_letter is not None:
            raise ValueError("revealed_letter must be null when correct is false")
        if self.score_delta != -5 or self.opponent_score_delta != 1:
            raise ValueError("score deltas must be -5/+1 when correct is false")
        if self.locks_enqueued != [self.cell_index]:
            raise ValueError("locks_enqueued must contain the guessed cell index when correct is false")
        return self

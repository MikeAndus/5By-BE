from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.enums import Topic


class AnswerQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_number: Literal[1, 2]
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class QuestionAnsweredEventData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_index: int = Field(ge=0, le=24)
    row: int = Field(ge=0, le=4)
    col: int = Field(ge=0, le=4)
    topic: Topic
    answer: str = Field(min_length=1)
    correct: bool
    revealed_letter: str | None = Field(default=None, min_length=1, max_length=1, pattern="^[A-Z]$")
    lock_cleared_cell_index: int | None = Field(default=None, ge=0, le=24)

    @model_validator(mode="after")
    def validate_correctness_fields(self) -> "QuestionAnsweredEventData":
        if self.correct and self.revealed_letter is None:
            raise ValueError("revealed_letter must be provided when correct is true")

        if not self.correct and self.revealed_letter is not None:
            raise ValueError("revealed_letter must be null when correct is false")

        return self

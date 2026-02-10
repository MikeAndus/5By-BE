from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.common import (
    SquareRef,
    ensure_five_ascii_letters,
    ensure_single_ascii_letter,
    normalize_trimmed,
    normalize_upper_trimmed,
)
from app.api.schemas.enums import Direction, Topic


class BaseMutatingRequest(BaseModel):
    player_number: Literal[1, 2]


class AskRequest(BaseMutatingRequest):
    square: SquareRef
    topic: Topic


class AnswerRequest(BaseMutatingRequest):
    answer: str = Field(min_length=1, max_length=2000)

    @field_validator("answer", mode="before")
    @classmethod
    def normalize_answer(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("answer must be a string")
        return normalize_trimmed(value)

    @field_validator("answer")
    @classmethod
    def validate_non_empty_answer(cls, value: str) -> str:
        if len(value) == 0:
            raise ValueError("answer must not be empty")
        if len(value) > 2000:
            raise ValueError("answer must be 1..2000 characters")
        return value


class GuessLetterRequest(BaseMutatingRequest):
    cell_index: int = Field(ge=0, le=24)
    letter: str

    @field_validator("letter", mode="before")
    @classmethod
    def normalize_letter(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("letter must be a string")
        return normalize_upper_trimmed(value)

    @field_validator("letter")
    @classmethod
    def validate_letter(cls, value: str) -> str:
        return ensure_single_ascii_letter(value)


class GuessWordRequest(BaseMutatingRequest):
    direction: Direction
    index: int = Field(ge=0, le=4)
    word: str

    @field_validator("word", mode="before")
    @classmethod
    def normalize_word(cls, value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("word must be a string")
        return normalize_upper_trimmed(value)

    @field_validator("word")
    @classmethod
    def validate_word(cls, value: str) -> str:
        return ensure_five_ascii_letters(value)


class SkipRequest(BaseMutatingRequest):
    pass


__all__ = [
    "AnswerRequest",
    "AskRequest",
    "BaseMutatingRequest",
    "GuessLetterRequest",
    "GuessWordRequest",
    "SkipRequest",
]

from __future__ import annotations

import re

from pydantic import BaseModel, Field, model_validator

from app.api.utils.grid import cell_index_from_row_col

_SINGLE_LETTER_RE = re.compile(r"^[A-Z]$")
_FIVE_LETTER_RE = re.compile(r"^[A-Z]{5}$")


class SquareRef(BaseModel):
    cell_index: int | None = Field(default=None, ge=0, le=24)
    row: int | None = Field(default=None, ge=0, le=4)
    col: int | None = Field(default=None, ge=0, le=4)

    @model_validator(mode="after")
    def validate_reference_shape(self) -> "SquareRef":
        has_cell_index = self.cell_index is not None
        has_row_col = self.row is not None or self.col is not None

        if has_cell_index and has_row_col:
            raise ValueError("Provide either cell_index or row/col, not both")

        if has_cell_index:
            return self

        if self.row is None or self.col is None:
            raise ValueError("Provide either cell_index or both row and col")

        return self

    def to_cell_index(self) -> int:
        if self.cell_index is not None:
            return self.cell_index
        if self.row is None or self.col is None:
            raise ValueError("Square reference is incomplete")
        return cell_index_from_row_col(self.row, self.col)


def normalize_trimmed(value: str) -> str:
    return value.strip()


def normalize_upper_trimmed(value: str) -> str:
    return normalize_trimmed(value).upper()


def ensure_single_ascii_letter(value: str) -> str:
    if not _SINGLE_LETTER_RE.fullmatch(value):
        raise ValueError("must be exactly one letter A-Z")
    return value


def ensure_five_ascii_letters(value: str) -> str:
    if not _FIVE_LETTER_RE.fullmatch(value):
        raise ValueError("must be exactly five letters A-Z")
    return value


__all__ = [
    "SquareRef",
    "ensure_five_ascii_letters",
    "ensure_single_ascii_letter",
    "normalize_trimmed",
    "normalize_upper_trimmed",
]

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.errors import ApiErrorCode, NotFoundError, RuleViolationError
from app.api.guards import (
    ensure_cell_not_locked_for_guess,
    ensure_cell_not_revealed,
    ensure_guess_word_cells_unlocked,
    ensure_in_progress,
    ensure_topic_allowed_and_unused,
    ensure_turn_owner,
    load_cell_state,
    load_session_or_404,
)
from app.api.schemas.common import SquareRef
from app.api.schemas.enums import Direction, Topic
from app.api.schemas.requests import AnswerRequest, GuessLetterRequest, GuessWordRequest
from app.api.schemas.snapshots import CellSnapshot, SessionSnapshot
from app.api.utils.grid import cell_index_from_row_col, row_col_from_cell_index
from app.db.models.cell_state import CellState
from app.db.models.enums import SessionStatus as DbSessionStatus
from app.db.models.session import Session


class _FakeScalars:
    def __init__(self, value: object) -> None:
        self._value = value

    def one_or_none(self) -> object:
        return self._value

    def all(self) -> list[object]:
        if isinstance(self._value, list):
            return self._value
        return [] if self._value is None else [self._value]


class _FakeResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._value)


def _make_session(status: DbSessionStatus = DbSessionStatus.IN_PROGRESS, current_turn: int = 1) -> Session:
    return Session(
        session_id=uuid4(),
        player_1_id=uuid4(),
        player_2_id=uuid4(),
        player_1_grid_id=uuid4(),
        player_2_grid_id=uuid4(),
        player_1_score=100,
        player_2_score=100,
        current_turn=current_turn,
        status=status,
    )


def _make_cell_state(
    *,
    player_id: int = 1,
    cell_index: int = 0,
    revealed: bool = False,
    locked: bool = False,
    topics_used: list[str] | None = None,
) -> CellState:
    return CellState(
        session_id=uuid4(),
        player_id=player_id,
        cell_index=cell_index,
        revealed=revealed,
        locked=locked,
        topics_used=topics_used or [],
    )


def test_square_ref_accepts_cell_index() -> None:
    square = SquareRef(cell_index=6)
    assert square.to_cell_index() == 6


def test_square_ref_accepts_row_col() -> None:
    square = SquareRef(row=2, col=3)
    assert square.to_cell_index() == 13


def test_square_ref_rejects_mixed_reference_forms() -> None:
    with pytest.raises(ValidationError):
        SquareRef(cell_index=0, row=0, col=0)


def test_square_ref_requires_complete_reference() -> None:
    with pytest.raises(ValidationError):
        SquareRef(row=1)


def test_grid_index_round_trip() -> None:
    index = cell_index_from_row_col(4, 4)
    assert index == 24
    assert row_col_from_cell_index(index) == (4, 4)


def test_guess_letter_request_normalizes_and_validates() -> None:
    request = GuessLetterRequest(player_number=1, cell_index=5, letter=" a ")
    assert request.letter == "A"

    with pytest.raises(ValidationError):
        GuessLetterRequest(player_number=1, cell_index=5, letter="AB")


def test_guess_word_request_normalizes_and_validates() -> None:
    request = GuessWordRequest(player_number=2, direction=Direction.DOWN, index=4, word="abcde")
    assert request.word == "ABCDE"

    with pytest.raises(ValidationError):
        GuessWordRequest(player_number=2, direction=Direction.ACROSS, index=1, word="AB1DE")


def test_answer_request_trims_and_rejects_blank() -> None:
    request = AnswerRequest(player_number=1, answer="  hello  ")
    assert request.answer == "hello"

    with pytest.raises(ValidationError):
        AnswerRequest(player_number=2, answer="   ")


def test_cell_snapshot_rejects_hidden_letter_and_invalid_topic() -> None:
    with pytest.raises(ValidationError):
        CellSnapshot(
            index=0,
            row=0,
            col=0,
            revealed=False,
            letter="A",
            locked=False,
            topics_used=[],
            revealed_by=None,
        )

    with pytest.raises(ValidationError):
        CellSnapshot(
            index=1,
            row=0,
            col=1,
            revealed=True,
            letter="A",
            locked=False,
            topics_used=["Unknown"],
            revealed_by=None,
        )


def test_session_snapshot_requires_two_players() -> None:
    player = {
        "player_number": 1,
        "name": None,
        "score": 100,
        "grid_id": uuid4(),
        "cells": [
            CellSnapshot(
                index=i,
                row=i // 5,
                col=i % 5,
                revealed=False,
                letter=None,
                locked=False,
                topics_used=[],
                revealed_by=None,
            )
            for i in range(25)
        ],
        "completed": False,
    }

    with pytest.raises(ValidationError):
        SessionSnapshot(
            session_id=uuid4(),
            status="in_progress",
            current_turn=1,
            players=[player, player],
            last_event=None,
        )


def test_ensure_in_progress_and_turn_owner_guards() -> None:
    ensure_in_progress(_make_session(status=DbSessionStatus.IN_PROGRESS))

    with pytest.raises(RuleViolationError) as not_in_progress:
        ensure_in_progress(_make_session(status=DbSessionStatus.COMPLETE))
    assert not_in_progress.value.code == ApiErrorCode.SESSION_NOT_IN_PROGRESS.value

    ensure_turn_owner(_make_session(current_turn=2), player_number=2)

    with pytest.raises(RuleViolationError) as out_of_turn:
        ensure_turn_owner(_make_session(current_turn=1), player_number=2)
    assert out_of_turn.value.code == ApiErrorCode.OUT_OF_TURN.value


def test_cell_state_guards() -> None:
    revealed_cell = _make_cell_state(revealed=True)
    with pytest.raises(RuleViolationError) as revealed_error:
        ensure_cell_not_revealed(revealed_cell)
    assert revealed_error.value.code == ApiErrorCode.CELL_ALREADY_REVEALED.value

    locked_cell = _make_cell_state(locked=True)
    with pytest.raises(RuleViolationError) as locked_error:
        ensure_cell_not_locked_for_guess(locked_cell)
    assert locked_error.value.code == ApiErrorCode.CELL_LOCKED.value


def test_topic_guard_rejects_reused_and_exhausted_topics() -> None:
    reused_topic_cell = _make_cell_state(topics_used=[Topic.SCIENCE.value])
    with pytest.raises(RuleViolationError) as reused_error:
        ensure_topic_allowed_and_unused(reused_topic_cell, Topic.SCIENCE)
    assert reused_error.value.code == ApiErrorCode.TOPIC_ALREADY_USED.value

    exhausted_topics_cell = _make_cell_state(
        topics_used=[
            Topic.POLITICS.value,
            Topic.SCIENCE.value,
            Topic.HISTORY.value,
            Topic.ART.value,
            Topic.CURRENT_AFFAIRS.value,
        ]
    )
    with pytest.raises(RuleViolationError) as exhausted_error:
        ensure_topic_allowed_and_unused(exhausted_topics_cell, Topic.SCIENCE)
    assert exhausted_error.value.code == ApiErrorCode.TOPIC_LIMIT_REACHED.value


@pytest.mark.asyncio
async def test_load_session_or_404_guard() -> None:
    db = AsyncMock()
    db.execute.return_value = _FakeResult(None)

    with pytest.raises(NotFoundError) as missing:
        await load_session_or_404(db, uuid4())
    assert missing.value.code == ApiErrorCode.SESSION_NOT_FOUND.value

    session = _make_session()
    db.execute.return_value = _FakeResult(session)
    loaded_session = await load_session_or_404(db, uuid4())
    assert loaded_session is session


@pytest.mark.asyncio
async def test_load_cell_state_and_guess_word_guards() -> None:
    db = AsyncMock()
    db.execute.return_value = _FakeResult(None)

    with pytest.raises(RuleViolationError) as missing_state:
        await load_cell_state(db, uuid4(), 1, 0)
    assert missing_state.value.code == ApiErrorCode.STATE_CORRUPT.value

    cells = []
    for i in range(5):
        cells.append(_make_cell_state(player_id=1, cell_index=i, revealed=(i == 0), locked=(i == 3)))

    db.execute.return_value = _FakeResult(cells)
    with pytest.raises(RuleViolationError) as locked_word:
        await ensure_guess_word_cells_unlocked(
            db=db,
            session_id=uuid4(),
            player_number=1,
            direction=Direction.ACROSS,
            index=0,
        )
    assert locked_word.value.code == ApiErrorCode.CELL_LOCKED.value

    cells_no_lock = [
        _make_cell_state(player_id=1, cell_index=i, revealed=(i == 0), locked=False)
        for i in range(5)
    ]
    db.execute.return_value = _FakeResult(cells_no_lock)
    loaded_cells = await ensure_guess_word_cells_unlocked(
        db=db,
        session_id=uuid4(),
        player_number=1,
        direction=Direction.ACROSS,
        index=0,
    )
    assert len(loaded_cells) == 5

from __future__ import annotations

import uuid

import pytest

from app.db.enums import EventTypeDbEnum, RevealedByDbEnum, SessionStatusDbEnum
from app.db.models.cell_lock import CellLock
from app.db.models.cell_state import CellState
from app.db.models.event_log import EventLog
from app.db.models.grid import Grid
from app.db.models.session import Session
from app.schemas.enums import GuessDirection
from app.services import session_guess

GRID_CELLS = "ABCDEFGHIJKLMNOPQRSTUVWXY"
WORDS_ACROSS = ["ABCDE", "FGHIJ", "KLMNO", "PQRST", "UVWXY"]
WORDS_DOWN = ["AFKPU", "BGLQV", "CHMRW", "DINSX", "EJOTY"]


class _ScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _BeginContext:
    def __init__(self, db: "_FakeDb") -> None:
        self._db = db

    async def __aenter__(self) -> "_FakeDb":
        self._db.begin_entries += 1
        return self._db

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        self._db.begin_exits += 1
        return False


class _FakeDb:
    def __init__(
        self,
        *,
        scalar_values: list[object] | None = None,
        scalars_values: list[list[object]] | None = None,
    ) -> None:
        self.scalar_values = list(scalar_values or [])
        self.scalars_values = list(scalars_values or [])
        self.added: list[object] = []
        self.flush_calls = 0
        self.begin_calls = 0
        self.begin_entries = 0
        self.begin_exits = 0

    def begin(self) -> _BeginContext:
        self.begin_calls += 1
        return _BeginContext(self)

    async def scalar(self, _query):  # noqa: ANN001
        if not self.scalar_values:
            raise AssertionError("Unexpected scalar() call")
        return self.scalar_values.pop(0)

    async def scalars(self, _query):  # noqa: ANN001
        if not self.scalars_values:
            raise AssertionError("Unexpected scalars() call")
        return _ScalarResult(self.scalars_values.pop(0))

    def add(self, row: object) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        self.flush_calls += 1


def _make_session(*, current_turn: int = 1) -> Session:
    return Session(
        id=uuid.uuid4(),
        status=SessionStatusDbEnum.IN_PROGRESS,
        current_turn=current_turn,
        player_1_grid_id=1,
        player_2_grid_id=2,
        player_1_name="P1",
        player_2_name="P2",
        player_1_score=100,
        player_2_score=100,
    )


def _make_grid(grid_id: int) -> Grid:
    return Grid(
        id=grid_id,
        cells=GRID_CELLS,
        words_across=WORDS_ACROSS,
        words_down=WORDS_DOWN,
    )


def _make_cell_state(
    *,
    session_id: uuid.UUID,
    player_number: int,
    cell_index: int,
    revealed: bool,
    locked: bool = False,
    revealed_by: RevealedByDbEnum | None = None,
) -> CellState:
    return CellState(
        session_id=session_id,
        player_number=player_number,
        cell_index=cell_index,
        revealed=revealed,
        locked=locked,
        letter=GRID_CELLS[cell_index] if revealed else None,
        revealed_by=revealed_by if revealed else None,
        topics_used=[],
    )


@pytest.mark.asyncio
async def test_guess_letter_correct_reveals_cell_and_emits_event(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _make_session(current_turn=1)
    cell_state = _make_cell_state(
        session_id=session.id,
        player_number=1,
        cell_index=12,
        revealed=False,
    )
    grid = _make_grid(1)
    db = _FakeDb(scalar_values=[session, cell_state, grid])

    snapshot = object()

    async def _fake_snapshot(*, session_id, db):  # noqa: ANN001
        assert session_id == session.id
        return snapshot

    monkeypatch.setattr(session_guess, "load_session_snapshot", _fake_snapshot)

    result = await session_guess.guess_letter(
        db=db,  # type: ignore[arg-type]
        session_id=session.id,
        player_number=1,
        cell_index=12,
        letter="m",
    )

    assert result is snapshot
    assert session.player_1_score == 100
    assert session.player_2_score == 100
    assert session.current_turn == 2
    assert cell_state.revealed is True
    assert cell_state.letter == "M"
    assert cell_state.revealed_by == RevealedByDbEnum.GUESS

    locks = [row for row in db.added if isinstance(row, CellLock)]
    events = [row for row in db.added if isinstance(row, EventLog)]
    assert locks == []
    assert len(events) == 1
    assert events[0].type == EventTypeDbEnum.LETTER_GUESSED
    assert events[0].event_data == {
        "cell_index": 12,
        "row": 2,
        "col": 2,
        "guessed_letter": "M",
        "correct": True,
        "revealed_letter": "M",
        "score_delta": 0,
        "opponent_score_delta": 0,
        "locks_enqueued": [],
        "auto_reveals": [],
    }


@pytest.mark.asyncio
async def test_guess_letter_incorrect_updates_scores_locks_and_event(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _make_session(current_turn=1)
    cell_state = _make_cell_state(
        session_id=session.id,
        player_number=1,
        cell_index=0,
        revealed=False,
    )
    grid = _make_grid(1)
    db = _FakeDb(scalar_values=[session, cell_state, grid])

    snapshot = object()

    async def _fake_snapshot(*, session_id, db):  # noqa: ANN001
        assert session_id == session.id
        return snapshot

    monkeypatch.setattr(session_guess, "load_session_snapshot", _fake_snapshot)

    result = await session_guess.guess_letter(
        db=db,  # type: ignore[arg-type]
        session_id=session.id,
        player_number=1,
        cell_index=0,
        letter="z",
    )

    assert result is snapshot
    assert session.player_1_score == 95
    assert session.player_2_score == 101
    assert session.current_turn == 2
    assert cell_state.revealed is False
    assert cell_state.locked is True

    locks = [row for row in db.added if isinstance(row, CellLock)]
    events = [row for row in db.added if isinstance(row, EventLog)]
    assert len(locks) == 1
    assert locks[0].cell_index == 0
    assert len(events) == 1
    assert events[0].type == EventTypeDbEnum.LETTER_GUESSED
    assert events[0].event_data == {
        "cell_index": 0,
        "row": 0,
        "col": 0,
        "guessed_letter": "Z",
        "correct": False,
        "revealed_letter": None,
        "score_delta": -5,
        "opponent_score_delta": 1,
        "locks_enqueued": [0],
        "auto_reveals": [],
    }


@pytest.mark.asyncio
async def test_guess_letter_rejects_locked_cell() -> None:
    session = _make_session(current_turn=1)
    cell_state = _make_cell_state(
        session_id=session.id,
        player_number=1,
        cell_index=7,
        revealed=False,
        locked=True,
    )
    db = _FakeDb(scalar_values=[session, cell_state])

    with pytest.raises(session_guess.CellLockedError):
        await session_guess.guess_letter(
            db=db,  # type: ignore[arg-type]
            session_id=session.id,
            player_number=1,
            cell_index=7,
            letter="A",
        )


@pytest.mark.asyncio
async def test_guess_letter_rejects_already_revealed_cell() -> None:
    session = _make_session(current_turn=1)
    cell_state = _make_cell_state(
        session_id=session.id,
        player_number=1,
        cell_index=9,
        revealed=True,
        revealed_by=RevealedByDbEnum.QUESTION,
    )
    db = _FakeDb(scalar_values=[session, cell_state])

    with pytest.raises(session_guess.CellAlreadyRevealedError):
        await session_guess.guess_letter(
            db=db,  # type: ignore[arg-type]
            session_id=session.id,
            player_number=1,
            cell_index=9,
            letter="A",
        )


@pytest.mark.asyncio
async def test_guess_letter_rejects_out_of_turn_player() -> None:
    session = _make_session(current_turn=2)
    db = _FakeDb(scalar_values=[session])

    with pytest.raises(session_guess.OutOfTurnError):
        await session_guess.guess_letter(
            db=db,  # type: ignore[arg-type]
            session_id=session.id,
            player_number=1,
            cell_index=9,
            letter="A",
        )


def _build_player_states(
    *,
    session_id: uuid.UUID,
    player_number: int,
    unrevealed_indices: set[int],
    locked_unrevealed_indices: set[int] | None = None,
) -> list[CellState]:
    locked_unrevealed = locked_unrevealed_indices or set()
    states: list[CellState] = []
    for cell_index in range(25):
        revealed = cell_index not in unrevealed_indices
        states.append(
            _make_cell_state(
                session_id=session_id,
                player_number=player_number,
                cell_index=cell_index,
                revealed=revealed,
                locked=cell_index in locked_unrevealed,
                revealed_by=RevealedByDbEnum.QUESTION if revealed else None,
            )
        )
    return states


@pytest.mark.asyncio
async def test_guess_word_correct_reveals_cells_and_auto_cascade(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _make_session(current_turn=1)
    states = _build_player_states(
        session_id=session.id,
        player_number=1,
        unrevealed_indices={0, 1, 2, 3, 4, 5, 10},
    )
    grid = _make_grid(1)
    db = _FakeDb(
        scalar_values=[session, grid],
        scalars_values=[states],
    )

    snapshot = object()

    async def _fake_snapshot(*, session_id, db):  # noqa: ANN001
        assert session_id == session.id
        return snapshot

    monkeypatch.setattr(session_guess, "load_session_snapshot", _fake_snapshot)

    result = await session_guess.guess_word(
        db=db,  # type: ignore[arg-type]
        session_id=session.id,
        player_number=1,
        direction=GuessDirection.ACROSS,
        index=0,
        word="abcde",
    )

    assert result is snapshot
    assert session.player_1_score == 100
    assert session.player_2_score == 100
    assert session.current_turn == 2

    by_index = {state.cell_index: state for state in states}
    for target in [0, 1, 2, 3, 4]:
        assert by_index[target].revealed is True
        assert by_index[target].revealed_by == RevealedByDbEnum.GUESS
    for auto in [5, 10]:
        assert by_index[auto].revealed is True
        assert by_index[auto].revealed_by == RevealedByDbEnum.AUTO

    locks = [row for row in db.added if isinstance(row, CellLock)]
    events = [row for row in db.added if isinstance(row, EventLog)]
    assert locks == []
    assert len(events) == 1
    assert events[0].type == EventTypeDbEnum.WORD_GUESSED
    assert events[0].event_data == {
        "direction": "across",
        "index": 0,
        "guessed_word": "ABCDE",
        "correct": True,
        "revealed_cells": [
            {"cell_index": 0, "row": 0, "col": 0, "revealed_letter": "A"},
            {"cell_index": 1, "row": 0, "col": 1, "revealed_letter": "B"},
            {"cell_index": 2, "row": 0, "col": 2, "revealed_letter": "C"},
            {"cell_index": 3, "row": 0, "col": 3, "revealed_letter": "D"},
            {"cell_index": 4, "row": 0, "col": 4, "revealed_letter": "E"},
        ],
        "score_delta": 0,
        "opponent_score_delta": 0,
        "locks_enqueued": [],
        "auto_reveals": [
            {"cell_index": 5, "row": 1, "col": 0, "revealed_letter": "F"},
            {"cell_index": 10, "row": 2, "col": 0, "revealed_letter": "K"},
        ],
    }


@pytest.mark.asyncio
async def test_guess_word_incorrect_locks_unrevealed_cells_in_ascending_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _make_session(current_turn=1)
    states = _build_player_states(
        session_id=session.id,
        player_number=1,
        unrevealed_indices={5, 10, 20},
    )
    grid = _make_grid(1)
    db = _FakeDb(
        scalar_values=[session, grid],
        scalars_values=[states],
    )

    snapshot = object()

    async def _fake_snapshot(*, session_id, db):  # noqa: ANN001
        assert session_id == session.id
        return snapshot

    monkeypatch.setattr(session_guess, "load_session_snapshot", _fake_snapshot)

    result = await session_guess.guess_word(
        db=db,  # type: ignore[arg-type]
        session_id=session.id,
        player_number=1,
        direction=GuessDirection.DOWN,
        index=0,
        word="ZZZZZ",
    )

    assert result is snapshot
    assert session.player_1_score == 95
    assert session.player_2_score == 101
    assert session.current_turn == 2

    by_index = {state.cell_index: state for state in states}
    assert by_index[5].locked is True
    assert by_index[10].locked is True
    assert by_index[20].locked is True

    locks = [row for row in db.added if isinstance(row, CellLock)]
    events = [row for row in db.added if isinstance(row, EventLog)]
    assert [row.cell_index for row in locks] == [5, 10, 20]
    assert len(events) == 1
    assert events[0].type == EventTypeDbEnum.WORD_GUESSED
    assert events[0].event_data == {
        "direction": "down",
        "index": 0,
        "guessed_word": "ZZZZZ",
        "correct": False,
        "revealed_cells": [],
        "score_delta": -5,
        "opponent_score_delta": 1,
        "locks_enqueued": [5, 10, 20],
        "auto_reveals": [],
    }


@pytest.mark.asyncio
async def test_guess_word_rejects_when_target_word_already_revealed() -> None:
    session = _make_session(current_turn=1)
    states = _build_player_states(
        session_id=session.id,
        player_number=1,
        unrevealed_indices=set(),
    )
    grid = _make_grid(1)
    db = _FakeDb(
        scalar_values=[session, grid],
        scalars_values=[states],
    )

    with pytest.raises(session_guess.WordAlreadyRevealedError):
        await session_guess.guess_word(
            db=db,  # type: ignore[arg-type]
            session_id=session.id,
            player_number=1,
            direction=GuessDirection.ACROSS,
            index=0,
            word="ABCDE",
        )


@pytest.mark.asyncio
async def test_guess_word_rejects_when_target_has_locked_unrevealed_cell() -> None:
    session = _make_session(current_turn=1)
    states = _build_player_states(
        session_id=session.id,
        player_number=1,
        unrevealed_indices={0},
        locked_unrevealed_indices={0},
    )
    grid = _make_grid(1)
    db = _FakeDb(
        scalar_values=[session, grid],
        scalars_values=[states],
    )

    with pytest.raises(session_guess.WordLockedError):
        await session_guess.guess_word(
            db=db,  # type: ignore[arg-type]
            session_id=session.id,
            player_number=1,
            direction=GuessDirection.ACROSS,
            index=0,
            word="ABCDE",
        )


@pytest.mark.asyncio
async def test_guess_word_rejects_out_of_turn_player() -> None:
    session = _make_session(current_turn=2)
    db = _FakeDb(scalar_values=[session])

    with pytest.raises(session_guess.OutOfTurnError):
        await session_guess.guess_word(
            db=db,  # type: ignore[arg-type]
            session_id=session.id,
            player_number=1,
            direction=GuessDirection.ACROSS,
            index=0,
            word="ABCDE",
        )

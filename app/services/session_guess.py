from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import EventTypeDbEnum, RevealedByDbEnum, SessionStatusDbEnum
from app.db.models.cell_lock import CellLock
from app.db.models.cell_state import CellState
from app.db.models.event_log import EventLog
from app.db.models.grid import Grid
from app.db.models.session import Session
from app.schemas.enums import GuessDirection
from app.schemas.guess_letter import LetterGuessedEventData
from app.schemas.guess_word import WordGuessedEventData
from app.schemas.session_snapshot import SessionSnapshot
from app.services.session_snapshot import load_session_snapshot


class SessionGuessError(Exception):
    pass


class SessionNotFoundError(SessionGuessError):
    pass


class SessionNotInProgressError(SessionGuessError):
    pass


class OutOfTurnError(SessionGuessError):
    pass


class CellAlreadyRevealedError(SessionGuessError):
    pass


class CellLockedError(SessionGuessError):
    pass


class WordAlreadyRevealedError(SessionGuessError):
    pass


class WordLockedError(SessionGuessError):
    pass


def _opponent(player_number: int) -> int:
    return 2 if player_number == 1 else 1


def _swap_turn(session: Session) -> None:
    session.current_turn = _opponent(session.current_turn)


def _grid_id_for_player(session: Session, player_number: int) -> int:
    return session.player_1_grid_id if player_number == 1 else session.player_2_grid_id


def _required_letter(grid_cells: str, cell_index: int) -> str:
    if len(grid_cells) != 25:
        raise RuntimeError("Grid cells payload is invalid; expected 25 letters")

    letter = grid_cells[cell_index].upper()
    if re.fullmatch(r"[A-Z]", letter) is None:
        raise RuntimeError("Grid letter is invalid; expected uppercase A-Z")

    return letter


def _word_cell_indices(direction: GuessDirection, index: int) -> list[int]:
    if direction == GuessDirection.ACROSS:
        return [index * 5 + offset for offset in range(5)]
    return [row * 5 + index for row in range(5)]


def _cell_obj(cell_index: int, revealed_letter: str) -> dict[str, Any]:
    return {
        "cell_index": cell_index,
        "row": cell_index // 5,
        "col": cell_index % 5,
        "revealed_letter": revealed_letter,
    }


def _get_required_word(grid: Grid, direction: GuessDirection, index: int) -> str:
    words = grid.words_across if direction == GuessDirection.ACROSS else grid.words_down
    if len(words) != 5:
        raise RuntimeError("Grid words payload is invalid; expected five words")
    return words[index].upper()


def _apply_wrong_guess_score(session: Session, player_number: int) -> None:
    if player_number == 1:
        session.player_1_score -= 5
        session.player_2_score += 1
    else:
        session.player_2_score -= 5
        session.player_1_score += 1


def _auto_reveal_cascade(
    *,
    cell_states_by_index: dict[int, CellState],
    grid_cells: str,
) -> list[dict[str, Any]]:
    auto_reveals: list[dict[str, Any]] = []

    while True:
        changed = False

        for direction in (GuessDirection.ACROSS, GuessDirection.DOWN):
            for index in range(5):
                indices = _word_cell_indices(direction, index)
                unrevealed = [
                    cell_states_by_index[cell_index]
                    for cell_index in indices
                    if not cell_states_by_index[cell_index].revealed
                ]
                if len(unrevealed) != 1:
                    continue

                target = unrevealed[0]
                if target.revealed:
                    continue

                revealed_letter = _required_letter(grid_cells, target.cell_index)
                target.revealed = True
                target.letter = revealed_letter
                target.revealed_by = RevealedByDbEnum.AUTO
                auto_reveals.append(_cell_obj(target.cell_index, revealed_letter))
                changed = True

        if not changed:
            break

    return auto_reveals


async def _load_and_lock_session(db: AsyncSession, session_id: UUID) -> Session:
    session = await db.scalar(
        select(Session)
        .where(Session.id == session_id)
        .with_for_update()
    )
    if session is None:
        raise SessionNotFoundError()
    return session


def _validate_turn_and_status(session: Session, player_number: int) -> None:
    if session.status != SessionStatusDbEnum.IN_PROGRESS:
        raise SessionNotInProgressError()
    if session.current_turn != player_number:
        raise OutOfTurnError()


async def guess_letter(
    db: AsyncSession,
    session_id: UUID,
    player_number: int,
    cell_index: int,
    letter: str,
) -> SessionSnapshot:
    guessed_letter = letter.upper()

    async with db.begin():
        session = await _load_and_lock_session(db=db, session_id=session_id)
        _validate_turn_and_status(session=session, player_number=player_number)

        cell_state = await db.scalar(
            select(CellState)
            .where(
                CellState.session_id == session_id,
                CellState.player_number == player_number,
                CellState.cell_index == cell_index,
            )
            .with_for_update()
        )
        if cell_state is None:
            raise RuntimeError("cell_state row missing for session/player/cell")
        if cell_state.revealed:
            raise CellAlreadyRevealedError()
        if cell_state.locked:
            raise CellLockedError()

        grid = await db.scalar(
            select(Grid).where(Grid.id == _grid_id_for_player(session=session, player_number=player_number))
        )
        if grid is None:
            raise RuntimeError("grid row missing for session player")

        required_letter = _required_letter(grid.cells, cell_index)
        correct = guessed_letter == required_letter

        if correct:
            cell_state.revealed = True
            cell_state.letter = required_letter
            cell_state.revealed_by = RevealedByDbEnum.GUESS
            score_delta = 0
            opponent_score_delta = 0
            revealed_letter = required_letter
            locks_enqueued: list[int] = []
        else:
            _apply_wrong_guess_score(session=session, player_number=player_number)
            db.add(
                CellLock(
                    session_id=session_id,
                    player_number=player_number,
                    cell_index=cell_index,
                    cleared_at=None,
                )
            )
            cell_state.locked = True
            score_delta = -5
            opponent_score_delta = 1
            revealed_letter = None
            locks_enqueued = [cell_index]

        _swap_turn(session)

        event_data = LetterGuessedEventData(
            cell_index=cell_index,
            row=cell_index // 5,
            col=cell_index % 5,
            guessed_letter=guessed_letter,
            correct=correct,
            revealed_letter=revealed_letter,
            score_delta=score_delta,
            opponent_score_delta=opponent_score_delta,
            locks_enqueued=locks_enqueued,
            auto_reveals=[],
        ).model_dump(mode="json")

        db.add(
            EventLog(
                session_id=session_id,
                player_number=player_number,
                type=EventTypeDbEnum.LETTER_GUESSED,
                event_data=event_data,
            )
        )
        await db.flush()

    return await load_session_snapshot(session_id=session_id, db=db)


async def guess_word(
    db: AsyncSession,
    session_id: UUID,
    player_number: int,
    direction: GuessDirection,
    index: int,
    word: str,
) -> SessionSnapshot:
    guessed_word = word.upper()
    target_indices = _word_cell_indices(direction, index)

    async with db.begin():
        session = await _load_and_lock_session(db=db, session_id=session_id)
        _validate_turn_and_status(session=session, player_number=player_number)

        player_cell_states = (
            await db.scalars(
                select(CellState)
                .where(
                    CellState.session_id == session_id,
                    CellState.player_number == player_number,
                )
                .order_by(CellState.cell_index.asc())
                .with_for_update()
            )
        ).all()
        if len(player_cell_states) != 25:
            raise RuntimeError("expected exactly 25 cell_state rows for player")

        cell_states_by_index = {cell_state.cell_index: cell_state for cell_state in player_cell_states}
        target_states = [cell_states_by_index[cell_index] for cell_index in target_indices]

        if all(cell_state.revealed for cell_state in target_states):
            raise WordAlreadyRevealedError()

        if any(cell_state.locked and not cell_state.revealed for cell_state in target_states):
            raise WordLockedError()

        grid = await db.scalar(
            select(Grid).where(Grid.id == _grid_id_for_player(session=session, player_number=player_number))
        )
        if grid is None:
            raise RuntimeError("grid row missing for session player")

        required_word = _get_required_word(grid=grid, direction=direction, index=index)
        correct = guessed_word == required_word

        if correct:
            revealed_cells: list[dict[str, Any]] = []
            for target_cell_index in sorted(target_indices):
                target_cell_state = cell_states_by_index[target_cell_index]
                if target_cell_state.revealed:
                    continue
                revealed_letter = _required_letter(grid.cells, target_cell_index)
                target_cell_state.revealed = True
                target_cell_state.letter = revealed_letter
                target_cell_state.revealed_by = RevealedByDbEnum.GUESS
                revealed_cells.append(_cell_obj(target_cell_index, revealed_letter))

            auto_reveals = _auto_reveal_cascade(
                cell_states_by_index=cell_states_by_index,
                grid_cells=grid.cells,
            )
            score_delta = 0
            opponent_score_delta = 0
            locks_enqueued: list[int] = []
        else:
            _apply_wrong_guess_score(session=session, player_number=player_number)
            locks_enqueued = sorted(
                cell_state.cell_index
                for cell_state in target_states
                if not cell_state.revealed
            )
            for lock_cell_index in locks_enqueued:
                db.add(
                    CellLock(
                        session_id=session_id,
                        player_number=player_number,
                        cell_index=lock_cell_index,
                        cleared_at=None,
                    )
                )
                cell_states_by_index[lock_cell_index].locked = True

            revealed_cells = []
            auto_reveals = []
            score_delta = -5
            opponent_score_delta = 1

        _swap_turn(session)

        event_data = WordGuessedEventData(
            direction=direction,
            index=index,
            guessed_word=guessed_word,
            correct=correct,
            revealed_cells=revealed_cells,
            score_delta=score_delta,
            opponent_score_delta=opponent_score_delta,
            locks_enqueued=locks_enqueued,
            auto_reveals=auto_reveals,
        ).model_dump(mode="json")

        db.add(
            EventLog(
                session_id=session_id,
                player_number=player_number,
                type=EventTypeDbEnum.WORD_GUESSED,
                event_data=event_data,
            )
        )
        await db.flush()

    return await load_session_snapshot(session_id=session_id, db=db)

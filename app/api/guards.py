from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiErrorCode, NotFoundError, RuleViolationError
from app.api.schemas.enums import Direction, Topic
from app.api.utils.grid import line_cell_indexes
from app.db.models.cell_state import CellState
from app.db.models.enums import SessionStatus as DbSessionStatus
from app.db.models.session import Session


async def load_session_or_404(db: AsyncSession, session_id: UUID) -> Session:
    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalars().one_or_none()
    if session is None:
        raise NotFoundError(code=ApiErrorCode.SESSION_NOT_FOUND)
    return session


def ensure_in_progress(session: Session) -> None:
    if session.status != DbSessionStatus.IN_PROGRESS:
        raise RuleViolationError(code=ApiErrorCode.SESSION_NOT_IN_PROGRESS)


def ensure_turn_owner(session: Session, player_number: int) -> None:
    if session.current_turn != player_number:
        raise RuleViolationError(code=ApiErrorCode.OUT_OF_TURN)


async def load_cell_state(db: AsyncSession, session_id: UUID, player_number: int, cell_index: int) -> CellState:
    result = await db.execute(
        select(CellState).where(
            CellState.session_id == session_id,
            CellState.player_id == player_number,
            CellState.cell_index == cell_index,
        )
    )
    cell_state = result.scalars().one_or_none()
    if cell_state is None:
        raise RuleViolationError(
            code=ApiErrorCode.STATE_CORRUPT,
            details={
                "session_id": str(session_id),
                "player_number": player_number,
                "cell_index": cell_index,
            },
        )
    return cell_state


def ensure_cell_not_revealed(cell_state: CellState) -> None:
    if cell_state.revealed:
        raise RuleViolationError(code=ApiErrorCode.CELL_ALREADY_REVEALED)


def ensure_cell_not_locked_for_guess(cell_state: CellState) -> None:
    if cell_state.locked:
        raise RuleViolationError(code=ApiErrorCode.CELL_LOCKED)


def ensure_topic_allowed_and_unused(cell_state: CellState, topic: Topic) -> None:
    topic_value = topic.value if isinstance(topic, Topic) else str(topic)
    topics_used = list(cell_state.topics_used or [])

    if len(topics_used) >= 5:
        raise RuleViolationError(code=ApiErrorCode.TOPIC_LIMIT_REACHED)

    if topic_value in topics_used:
        raise RuleViolationError(code=ApiErrorCode.TOPIC_ALREADY_USED)


async def ensure_guess_word_cells_unlocked(
    db: AsyncSession,
    session_id: UUID,
    player_number: int,
    direction: Direction,
    index: int,
) -> list[CellState]:
    target_cell_indexes = line_cell_indexes(direction.value, index)
    result = await db.execute(
        select(CellState).where(
            CellState.session_id == session_id,
            CellState.player_id == player_number,
            CellState.cell_index.in_(target_cell_indexes),
        )
    )
    cell_states = result.scalars().all()

    if len(cell_states) != len(target_cell_indexes):
        raise RuleViolationError(
            code=ApiErrorCode.STATE_CORRUPT,
            details={
                "session_id": str(session_id),
                "player_number": player_number,
                "direction": direction.value,
                "index": index,
            },
        )

    for cell_state in cell_states:
        if not cell_state.revealed and cell_state.locked:
            raise RuleViolationError(
                code=ApiErrorCode.CELL_LOCKED,
                details={
                    "cell_index": cell_state.cell_index,
                    "rule": "guess_word_cannot_include_locked_unrevealed_cells",
                },
            )

    return cell_states


async def ensure_session_ready_for_mutation(db: AsyncSession, session_id: UUID, player_number: int) -> Session:
    session = await load_session_or_404(db, session_id)
    ensure_in_progress(session)
    ensure_turn_owner(session, player_number)
    return session


async def ensure_pending_question_exists(db: AsyncSession, session_id: UUID, player_number: int) -> None:
    # Placeholder hook for BE-3/BE-4 once pending-question persistence exists.
    _ = (db, session_id, player_number)


__all__ = [
    "ensure_cell_not_locked_for_guess",
    "ensure_cell_not_revealed",
    "ensure_guess_word_cells_unlocked",
    "ensure_in_progress",
    "ensure_pending_question_exists",
    "ensure_session_ready_for_mutation",
    "ensure_topic_allowed_and_unused",
    "ensure_turn_owner",
    "load_cell_state",
    "load_session_or_404",
]

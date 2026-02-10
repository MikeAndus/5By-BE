from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiErrorCode, RuleViolationError
from app.api.guards import (
    ensure_cell_not_locked_for_guess,
    ensure_cell_not_revealed,
    ensure_guess_word_cells_unlocked,
    ensure_pending_question_exists,
    ensure_session_ready_for_mutation,
    ensure_topic_allowed_and_unused,
    load_cell_state,
    load_session_or_404,
)
from app.api.schemas.enums import SessionStatus
from app.api.schemas.requests import (
    AnswerRequest,
    AskRequest,
    GuessLetterRequest,
    GuessWordRequest,
    SkipRequest,
)
from app.api.schemas.snapshots import (
    CellSnapshot,
    LastEventSnapshot,
    PlayerSnapshot,
    SessionSnapshot,
)
from app.api.utils.grid import row_col_from_cell_index
from app.db.models.cell_state import CellState
from app.db.models.event_log import EventLog
from app.db.models.grid import Grid
from app.db.models.session import Session
from app.db.session import get_async_session

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=501)
async def create_session_placeholder() -> None:
    raise HTTPException(status_code=501, detail="Session creation is not implemented in BE-2-2")


def _build_last_event_snapshot(event: EventLog | None) -> LastEventSnapshot | None:
    if event is None:
        return None

    event_result = None
    message_to_speak = None

    if isinstance(event.event_data, dict):
        event_result = event.event_data.get("result")
        message_to_speak = event.event_data.get("message_to_speak")

    if event_result not in {"ok", "error"}:
        event_result = None

    return LastEventSnapshot(
        type=event.event_type.value,
        result=event_result,
        message_to_speak=message_to_speak,
    )


def _build_player_snapshots(
    session_id: UUID,
    session: Session,
    cell_states: list[CellState],
    player_grid_cells: dict[int, str | None],
) -> list[PlayerSnapshot]:
    cells_by_player: dict[int, list[CellSnapshot]] = {1: [], 2: []}

    for cell_state in cell_states:
        if cell_state.player_id not in cells_by_player:
            raise RuleViolationError(
                code=ApiErrorCode.STATE_CORRUPT,
                details={
                    "session_id": str(session_id),
                    "player_id": cell_state.player_id,
                    "rule": "player_id_must_be_1_or_2",
                },
            )
        row, col = row_col_from_cell_index(cell_state.cell_index)
        player_cells = player_grid_cells.get(cell_state.player_id)
        if player_cells is None or len(player_cells) != 25:
            raise RuleViolationError(
                code=ApiErrorCode.STATE_CORRUPT,
                details={
                    "session_id": str(session_id),
                    "player_id": cell_state.player_id,
                    "rule": "grid_cells_must_be_present_and_length_25",
                },
            )
        cells_by_player[cell_state.player_id].append(
            CellSnapshot(
                index=cell_state.cell_index,
                row=row,
                col=col,
                revealed=cell_state.revealed,
                letter=player_cells[cell_state.cell_index] if cell_state.revealed else None,
                locked=cell_state.locked,
                topics_used=list(cell_state.topics_used or []),
                revealed_by=(cell_state.revealed_by.value if cell_state.revealed_by else None),
            )
        )

    for player_number in (1, 2):
        cells_by_player[player_number].sort(key=lambda cell: cell.index)

    if len(cells_by_player[1]) != 25 or len(cells_by_player[2]) != 25:
        raise RuleViolationError(
            code=ApiErrorCode.STATE_CORRUPT,
            details={
                "session_id": str(session_id),
                "player_1_cell_count": len(cells_by_player[1]),
                "player_2_cell_count": len(cells_by_player[2]),
            },
        )

    return [
        PlayerSnapshot(
            player_number=1,
            name=session.player_1_name,
            score=session.player_1_score,
            grid_id=session.player_1_grid_id,
            cells=cells_by_player[1],
            completed=all(cell.revealed for cell in cells_by_player[1]),
        ),
        PlayerSnapshot(
            player_number=2,
            name=session.player_2_name,
            score=session.player_2_score,
            grid_id=session.player_2_grid_id,
            cells=cells_by_player[2],
            completed=all(cell.revealed for cell in cells_by_player[2]),
        ),
    ]


async def _build_session_snapshot(db: AsyncSession, session_id: UUID) -> SessionSnapshot:
    session = await load_session_or_404(db, session_id)

    cell_states_result = await db.execute(select(CellState).where(CellState.session_id == session_id))
    cell_states = cell_states_result.scalars().all()

    grid_result = await db.execute(
        select(Grid).where(Grid.grid_id.in_([session.player_1_grid_id, session.player_2_grid_id]))
    )
    grids = {grid.grid_id: grid for grid in grid_result.scalars().all()}
    player_grid_cells = {
        1: grids.get(session.player_1_grid_id).cells if session.player_1_grid_id in grids else None,
        2: grids.get(session.player_2_grid_id).cells if session.player_2_grid_id in grids else None,
    }

    last_event_result = await db.execute(
        select(EventLog)
        .where(EventLog.session_id == session_id)
        .order_by(desc(EventLog.timestamp), desc(EventLog.created_at))
        .limit(1)
    )
    last_event = last_event_result.scalars().one_or_none()

    return SessionSnapshot(
        session_id=session.session_id,
        status=SessionStatus(session.status.value),
        current_turn=session.current_turn,
        players=_build_player_snapshots(session_id, session, cell_states, player_grid_cells),
        last_event=_build_last_event_snapshot(last_event),
    )


@router.get("/{session_id}", response_model=SessionSnapshot)
async def get_session_snapshot(
    session_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    return await _build_session_snapshot(db, session_id)


@router.post("/{session_id}/ask", response_model=SessionSnapshot)
async def ask_question(
    session_id: UUID,
    payload: AskRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    await ensure_session_ready_for_mutation(db, session_id, payload.player_number)

    cell_index = payload.square.to_cell_index()
    cell_state = await load_cell_state(db, session_id, payload.player_number, cell_index)
    ensure_cell_not_revealed(cell_state)
    ensure_topic_allowed_and_unused(cell_state, payload.topic)

    # Placeholder: BE-3/BE-4 will persist mutation effects.
    return await _build_session_snapshot(db, session_id)


@router.post("/{session_id}/answer", response_model=SessionSnapshot)
async def submit_answer(
    session_id: UUID,
    payload: AnswerRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    await ensure_session_ready_for_mutation(db, session_id, payload.player_number)
    await ensure_pending_question_exists(db, session_id, payload.player_number)

    # Placeholder: BE-3/BE-4 will persist mutation effects.
    return await _build_session_snapshot(db, session_id)


@router.post("/{session_id}/guess-letter", response_model=SessionSnapshot)
async def guess_letter(
    session_id: UUID,
    payload: GuessLetterRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    await ensure_session_ready_for_mutation(db, session_id, payload.player_number)

    cell_state = await load_cell_state(db, session_id, payload.player_number, payload.cell_index)
    ensure_cell_not_revealed(cell_state)
    ensure_cell_not_locked_for_guess(cell_state)

    # Placeholder: BE-3/BE-4 will persist mutation effects.
    return await _build_session_snapshot(db, session_id)


@router.post("/{session_id}/guess-word", response_model=SessionSnapshot)
async def guess_word(
    session_id: UUID,
    payload: GuessWordRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    await ensure_session_ready_for_mutation(db, session_id, payload.player_number)

    await ensure_guess_word_cells_unlocked(
        db=db,
        session_id=session_id,
        player_number=payload.player_number,
        direction=payload.direction,
        index=payload.index,
    )

    # Placeholder: BE-3/BE-4 will persist mutation effects.
    return await _build_session_snapshot(db, session_id)


@router.post("/{session_id}/skip", response_model=SessionSnapshot)
async def skip_turn(
    session_id: UUID,
    payload: SkipRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    await ensure_session_ready_for_mutation(db, session_id, payload.player_number)

    # Placeholder: BE-3/BE-4 will persist mutation effects.
    return await _build_session_snapshot(db, session_id)


__all__ = ["router"]

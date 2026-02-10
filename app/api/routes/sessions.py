from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.guards import (
    ensure_cell_not_locked_for_guess,
    ensure_cell_not_revealed,
    ensure_guess_word_cells_unlocked,
    ensure_pending_question_exists,
    ensure_session_ready_for_mutation,
    ensure_topic_allowed_and_unused,
    load_cell_state,
)
from app.api.schemas.requests import (
    AnswerRequest,
    AskRequest,
    GuessLetterRequest,
    GuessWordRequest,
    SkipRequest,
)
from app.api.schemas.snapshots import SessionSnapshot
from app.db.session import get_async_session
from app.game.sessions import create_session as create_game_session
from app.game.state_snapshot import build_state_snapshot
from app.schemas.sessions import CreateSessionRequest

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=201, response_model=SessionSnapshot)
async def create_session(
    payload: CreateSessionRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    return await create_game_session(
        db,
        player_1_name=payload.player_1_name,
        player_2_name=payload.player_2_name,
    )


@router.get("/{session_id}", response_model=SessionSnapshot)
async def get_session_snapshot(
    session_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    return await build_state_snapshot(db, session_id)


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
    return await build_state_snapshot(db, session_id)


@router.post("/{session_id}/answer", response_model=SessionSnapshot)
async def submit_answer(
    session_id: UUID,
    payload: AnswerRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    await ensure_session_ready_for_mutation(db, session_id, payload.player_number)
    await ensure_pending_question_exists(db, session_id, payload.player_number)

    # Placeholder: BE-3/BE-4 will persist mutation effects.
    return await build_state_snapshot(db, session_id)


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
    return await build_state_snapshot(db, session_id)


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
    return await build_state_snapshot(db, session_id)


@router.post("/{session_id}/skip", response_model=SessionSnapshot)
async def skip_turn(
    session_id: UUID,
    payload: SkipRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    await ensure_session_ready_for_mutation(db, session_id, payload.player_number)

    # Placeholder: BE-3/BE-4 will persist mutation effects.
    return await build_state_snapshot(db, session_id)


__all__ = ["router"]

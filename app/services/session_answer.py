from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import EventTypeDbEnum, RevealedByDbEnum, SessionStatusDbEnum
from app.db.models.cell_lock import CellLock
from app.db.models.cell_state import CellState
from app.db.models.event_log import EventLog
from app.db.models.grid import Grid
from app.db.models.session import Session
from app.schemas.answer_question import QuestionAnsweredEventData
from app.schemas.ask_question import QuestionAskedEventData
from app.schemas.session_snapshot import SessionSnapshot
from app.services.session_ask import _get_required_letter
from app.services.session_snapshot import load_session_snapshot

SESSION_NOT_FOUND_DETAIL = {
    "code": "session_not_found",
    "message": "Session not found",
}

SESSION_NOT_IN_PROGRESS_DETAIL = {
    "code": "session_not_in_progress",
    "message": "Session is not in progress",
}

OUT_OF_TURN_DETAIL = {
    "code": "out_of_turn",
    "message": "It is not this player's turn",
}

NO_PENDING_QUESTION_DETAIL = {
    "code": "no_pending_question",
    "message": "No pending question to answer",
}


async def answer_question(
    *,
    db: AsyncSession,
    session_id: uuid.UUID,
    player_number: int,
    answer: str,
) -> SessionSnapshot:
    snapshot: SessionSnapshot | None = None

    async with db.begin():
        session = await db.scalar(
            select(Session)
            .where(Session.id == session_id)
            .with_for_update()
        )
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SESSION_NOT_FOUND_DETAIL,
            )

        if session.status != SessionStatusDbEnum.IN_PROGRESS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=SESSION_NOT_IN_PROGRESS_DETAIL,
            )

        if session.current_turn != player_number:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=OUT_OF_TURN_DETAIL,
            )

        asked_event = await db.scalar(
            select(EventLog)
            .where(
                EventLog.session_id == session_id,
                EventLog.player_number == player_number,
                EventLog.type == EventTypeDbEnum.QUESTION_ASKED,
            )
            .order_by(EventLog.created_at.desc(), EventLog.id.desc())
            .limit(1)
        )

        answered_event = await db.scalar(
            select(EventLog)
            .where(
                EventLog.session_id == session_id,
                EventLog.player_number == player_number,
                EventLog.type == EventTypeDbEnum.QUESTION_ANSWERED,
            )
            .order_by(EventLog.created_at.desc(), EventLog.id.desc())
            .limit(1)
        )

        has_pending_question = (
            asked_event is not None
            and (answered_event is None or answered_event.created_at < asked_event.created_at)
        )
        if not has_pending_question or asked_event is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=NO_PENDING_QUESTION_DETAIL,
            )

        try:
            asked_event_data = QuestionAskedEventData.model_validate(asked_event.event_data)
        except ValidationError as exc:
            raise RuntimeError("Invalid question_asked event_data") from exc

        submitted_trimmed = answer.strip()
        submitted_casefold = submitted_trimmed.casefold()
        variants_norm = [variant.strip().casefold() for variant in asked_event_data.acceptable_variants]
        correct = submitted_casefold in variants_norm

        revealed_letter: str | None = None
        lock_cleared_cell_index: int | None = None

        if correct:
            grid_id = session.player_1_grid_id if player_number == 1 else session.player_2_grid_id
            grid_cells = await db.scalar(select(Grid.cells).where(Grid.id == grid_id))
            if grid_cells is None:
                raise RuntimeError("grid row missing for session player")

            required_letter = _get_required_letter(
                grid_cells=grid_cells,
                cell_index=asked_event_data.cell_index,
            )

            target_cell_state = await db.scalar(
                select(CellState)
                .where(
                    CellState.session_id == session_id,
                    CellState.player_number == player_number,
                    CellState.cell_index == asked_event_data.cell_index,
                )
                .with_for_update()
            )
            if target_cell_state is None:
                raise RuntimeError("cell_state row missing for pending question cell")

            target_cell_state.revealed = True
            target_cell_state.letter = required_letter
            target_cell_state.revealed_by = RevealedByDbEnum.QUESTION
            revealed_letter = required_letter

            oldest_uncleared_lock = await db.scalar(
                select(CellLock)
                .where(
                    CellLock.session_id == session_id,
                    CellLock.player_number == player_number,
                    CellLock.cleared_at.is_(None),
                )
                .order_by(CellLock.created_at.asc(), CellLock.id.asc())
                .with_for_update()
                .limit(1)
            )

            if oldest_uncleared_lock is not None:
                oldest_uncleared_lock.cleared_at = datetime.now(timezone.utc)
                lock_cleared_cell_index = oldest_uncleared_lock.cell_index

                remaining_uncleared_count = await db.scalar(
                    select(func.count(CellLock.id))
                    .where(
                        CellLock.session_id == session_id,
                        CellLock.player_number == player_number,
                        CellLock.cell_index == oldest_uncleared_lock.cell_index,
                        CellLock.cleared_at.is_(None),
                    )
                )
                has_remaining_locks = (remaining_uncleared_count or 0) > 0

                cleared_cell_state = await db.scalar(
                    select(CellState)
                    .where(
                        CellState.session_id == session_id,
                        CellState.player_number == player_number,
                        CellState.cell_index == oldest_uncleared_lock.cell_index,
                    )
                    .with_for_update()
                )
                if cleared_cell_state is None:
                    raise RuntimeError("cell_state row missing for cleared lock cell")
                cleared_cell_state.locked = has_remaining_locks

        session.current_turn = 2 if player_number == 1 else 1

        event_data = QuestionAnsweredEventData(
            cell_index=asked_event_data.cell_index,
            row=asked_event_data.row,
            col=asked_event_data.col,
            topic=asked_event_data.topic,
            answer=submitted_trimmed,
            correct=correct,
            revealed_letter=revealed_letter,
            lock_cleared_cell_index=lock_cleared_cell_index,
        ).model_dump(mode="json")

        db.add(
            EventLog(
                session_id=session_id,
                player_number=player_number,
                type=EventTypeDbEnum.QUESTION_ANSWERED,
                event_data=event_data,
            )
        )
        await db.flush()

        snapshot = await load_session_snapshot(session_id=session_id, db=db)

    if snapshot is None:
        raise RuntimeError("failed to load session snapshot after answer update")

    return snapshot

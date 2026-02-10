from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.enums import EventTypeDbEnum, SessionStatusDbEnum, TopicDbEnum
from app.db.models.cell_state import CellState
from app.db.models.event_log import EventLog
from app.db.models.grid import Grid
from app.db.models.session import Session
from app.schemas.ask_question import QuestionAskedEventData
from app.schemas.enums import Topic
from app.schemas.session_snapshot import SessionSnapshot
from app.services.session_snapshot import load_session_snapshot
from app.services.trivia_generator_stub import generate_stub_question

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

TOPICS_EXHAUSTED_DETAIL = {
    "code": "topics_exhausted",
    "message": "No topics remaining for this cell",
}


def _get_required_letter(grid_cells: str, cell_index: int) -> str:
    if len(grid_cells) != 25:
        raise RuntimeError("Grid cells payload is invalid; expected 25 letters")

    required_letter = grid_cells[cell_index]
    if re.fullmatch(r"[A-Z]", required_letter) is None:
        raise RuntimeError("Grid letter is invalid; expected uppercase A-Z")

    return required_letter


async def ask_question(
    *,
    db: AsyncSession,
    session_id: uuid.UUID,
    player_number: int,
    cell_index: int,
    topic: Topic,
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

        existing_topics = list(cell_state.topics_used or [])
        if len(existing_topics) >= 5:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=TOPICS_EXHAUSTED_DETAIL,
            )

        if player_number == 1:
            session.player_1_score -= 1
            grid_id = session.player_1_grid_id
        else:
            session.player_2_score -= 1
            grid_id = session.player_2_grid_id

        cell_state.topics_used = [*existing_topics, TopicDbEnum(topic.value)]

        grid_cells = await db.scalar(select(Grid.cells).where(Grid.id == grid_id))
        if grid_cells is None:
            raise RuntimeError("grid row missing for session player")

        required_letter = _get_required_letter(grid_cells=grid_cells, cell_index=cell_index)

        generator_mode = get_settings().trivia_generator_mode
        if generator_mode not in {"stub", "openai"}:
            raise RuntimeError("Unsupported trivia generator mode")

        # Phase 3 always uses stub generation even when mode=openai is configured.
        generated = generate_stub_question(topic=topic, required_letter=required_letter, cell_index=cell_index)

        event_data = QuestionAskedEventData(
            cell_index=cell_index,
            row=cell_index // 5,
            col=cell_index % 5,
            topic=topic,
            question_text=generated.question_text,
            answer=generated.answer,
            acceptable_variants=generated.acceptable_variants,
            generator="stub_v1",
        ).model_dump(mode="json")

        db.add(
            EventLog(
                session_id=session_id,
                player_number=player_number,
                type=EventTypeDbEnum.QUESTION_ASKED,
                event_data=event_data,
            )
        )

        await db.flush()
        snapshot = await load_session_snapshot(session_id=session_id, db=db)

    if snapshot is None:
        raise RuntimeError("failed to load session snapshot after ask update")

    return snapshot

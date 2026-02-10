from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, status
from pydantic import ValidationError
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
from app.services.openai_client import OpenAIClientUnavailableError
from app.services.session_snapshot import load_session_snapshot
from app.services.trivia_generator_openai import OpenAiGenerationFailedError, generate_openai_question
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

OPENAI_UNAVAILABLE_DETAIL = {
    "code": "openai_unavailable",
    "message": "Trivia generation is temporarily unavailable",
}


def _get_required_letter(grid_cells: str, cell_index: int) -> str:
    if len(grid_cells) != 25:
        raise RuntimeError("Grid cells payload is invalid; expected 25 letters")

    required_letter = grid_cells[cell_index]
    if re.fullmatch(r"[A-Z]", required_letter) is None:
        raise RuntimeError("Grid letter is invalid; expected uppercase A-Z")

    return required_letter


async def _get_prior_questions(
    *,
    db: AsyncSession,
    session_id: uuid.UUID,
    player_number: int,
    cell_index: int,
) -> list[str]:
    rows = (
        await db.scalars(
            select(EventLog.event_data)
            .where(
                EventLog.session_id == session_id,
                EventLog.player_number == player_number,
                EventLog.type == EventTypeDbEnum.QUESTION_ASKED,
            )
            .order_by(EventLog.created_at.desc(), EventLog.id.desc())
            .limit(50)
        )
    ).all()

    prior_questions_desc: list[str] = []
    for event_data in rows:
        try:
            parsed = QuestionAskedEventData.model_validate(event_data)
        except ValidationError as exc:
            raise RuntimeError("Invalid question_asked event_data found while loading prior questions") from exc
        if parsed.cell_index == cell_index:
            prior_questions_desc.append(parsed.question_text)
            if len(prior_questions_desc) >= 10:
                break

    prior_questions_desc.reverse()
    return prior_questions_desc


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

        cell_state.topics_used = [*existing_topics, TopicDbEnum[topic.name]]

        grid_cells = await db.scalar(select(Grid.cells).where(Grid.id == grid_id))
        if grid_cells is None:
            raise RuntimeError("grid row missing for session player")

        required_letter = _get_required_letter(grid_cells=grid_cells, cell_index=cell_index)

        generator_mode = get_settings().trivia_generator_mode
        if generator_mode not in {"stub", "openai"}:
            raise RuntimeError("Unsupported trivia generator mode")

        generated_payload: dict[str, object]
        generator_name: str
        successful_openai_attempt = None

        if generator_mode == "stub":
            generated = generate_stub_question(topic=topic, required_letter=required_letter, cell_index=cell_index)
            generated_payload = {
                "question_text": generated.question_text,
                "answer": generated.answer,
                "acceptable_variants": generated.acceptable_variants,
            }
            generator_name = "stub_v1"
        else:
            prior_questions = await _get_prior_questions(
                db=db,
                session_id=session_id,
                player_number=player_number,
                cell_index=cell_index,
            )
            try:
                generated_payload, successful_openai_attempt = await generate_openai_question(
                    session_id=session_id,
                    player_number=player_number,
                    cell_index=cell_index,
                    topic=topic,
                    required_letter=required_letter,
                    prior_questions=prior_questions,
                    db=db,
                )
            except (OpenAIClientUnavailableError, OpenAiGenerationFailedError):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=OPENAI_UNAVAILABLE_DETAIL,
                ) from None

            generator_name = "openai_responses_v1"

        event_data = QuestionAskedEventData(
            cell_index=cell_index,
            row=cell_index // 5,
            col=cell_index % 5,
            topic=topic,
            question_text=str(generated_payload["question_text"]),
            answer=str(generated_payload["answer"]),
            acceptable_variants=[str(item) for item in generated_payload["acceptable_variants"]],
            generator=generator_name,
        ).model_dump(mode="json")

        event_log = EventLog(
            session_id=session_id,
            player_number=player_number,
            type=EventTypeDbEnum.QUESTION_ASKED,
            event_data=event_data,
        )
        db.add(event_log)

        await db.flush()

        if successful_openai_attempt is not None:
            successful_openai_attempt.event_log_id = event_log.id
            await db.flush()

        snapshot = await load_session_snapshot(session_id=session_id, db=db)

    if snapshot is None:
        raise RuntimeError("failed to load session snapshot after ask update")

    return snapshot

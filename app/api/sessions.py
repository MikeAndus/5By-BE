import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.answer_question import AnswerQuestionRequest
from app.schemas.ask_question import AskQuestionRequest
from app.schemas.create_session import CreateSessionRequest
from app.schemas.guess_letter import GuessLetterRequest
from app.schemas.guess_word import GuessWordRequest
from app.schemas.session_snapshot import SessionSnapshot
from app.services.rate_limit import enforce_ask_rate_limit
from app.services.session_answer import answer_question
from app.services.session_create import GridsUnavailableError, create_session
from app.services.session_guess import (
    CellAlreadyRevealedError,
    CellLockedError,
    OutOfTurnError,
    SessionNotFoundError,
    SessionNotInProgressError,
    WordAlreadyRevealedError,
    WordLockedError,
    guess_letter,
    guess_word,
)
from app.services.session_ask import ask_question
from app.services.session_snapshot import SessionSnapshotNotFoundError, load_session_snapshot

router = APIRouter(prefix="/sessions", tags=["sessions"])

SESSION_NOT_FOUND_DETAIL = {
    "code": "session_not_found",
    "message": "Session not found",
}

GRIDS_UNAVAILABLE_DETAIL = {
    "code": "grids_unavailable",
    "message": "Not enough grids available to create a session",
}

SESSION_NOT_IN_PROGRESS_DETAIL = {
    "code": "session_not_in_progress",
    "message": "Session is not in progress",
}

OUT_OF_TURN_DETAIL = {
    "code": "out_of_turn",
    "message": "It is not this player's turn",
}

CELL_ALREADY_REVEALED_DETAIL = {
    "code": "cell_already_revealed",
    "message": "Cell is already revealed",
}

CELL_LOCKED_DETAIL = {
    "code": "cell_locked",
    "message": "Cell is locked",
}

WORD_ALREADY_REVEALED_DETAIL = {
    "code": "word_already_revealed",
    "message": "Word is already fully revealed",
}

WORD_LOCKED_DETAIL = {
    "code": "word_locked",
    "message": "Word contains locked cells",
}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SessionSnapshot)
async def create_session_endpoint(
    payload: CreateSessionRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    request = payload or CreateSessionRequest()

    try:
        session_id = await create_session(
            db=db,
            player_1_name=request.player_1_name,
            player_2_name=request.player_2_name,
        )
    except GridsUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=GRIDS_UNAVAILABLE_DETAIL,
        ) from None

    return await load_session_snapshot(session_id=session_id, db=db)


@router.get("/{session_id}", response_model=SessionSnapshot)
async def get_session_snapshot(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    try:
        return await load_session_snapshot(session_id=session_id, db=db)
    except SessionSnapshotNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=SESSION_NOT_FOUND_DETAIL,
        ) from None


@router.post("/{session_id}/ask", response_model=SessionSnapshot)
async def ask_question_endpoint(
    session_id: uuid.UUID,
    request: Request,
    payload: AskQuestionRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    await enforce_ask_rate_limit(
        session_id=session_id,
        client_ip=request.client.host if request.client is not None else None,
    )

    return await ask_question(
        db=db,
        session_id=session_id,
        player_number=payload.player_number,
        cell_index=payload.cell_index,
        topic=payload.topic,
    )


@router.post("/{session_id}/answer", response_model=SessionSnapshot)
async def answer_question_endpoint(
    session_id: uuid.UUID,
    payload: AnswerQuestionRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    return await answer_question(
        db=db,
        session_id=session_id,
        player_number=payload.player_number,
        answer=payload.answer,
    )


@router.post("/{session_id}/guess-letter", response_model=SessionSnapshot)
async def guess_letter_endpoint(
    session_id: uuid.UUID,
    payload: GuessLetterRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    try:
        return await guess_letter(
            db=db,
            session_id=session_id,
            player_number=payload.player_number,
            cell_index=payload.cell_index,
            letter=payload.letter,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_DETAIL) from None
    except SessionNotInProgressError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=SESSION_NOT_IN_PROGRESS_DETAIL,
        ) from None
    except OutOfTurnError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=OUT_OF_TURN_DETAIL) from None
    except CellAlreadyRevealedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=CELL_ALREADY_REVEALED_DETAIL,
        ) from None
    except CellLockedError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=CELL_LOCKED_DETAIL) from None


@router.post("/{session_id}/guess-word", response_model=SessionSnapshot)
async def guess_word_endpoint(
    session_id: uuid.UUID,
    payload: GuessWordRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    try:
        return await guess_word(
            db=db,
            session_id=session_id,
            player_number=payload.player_number,
            direction=payload.direction,
            index=payload.index,
            word=payload.word,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=SESSION_NOT_FOUND_DETAIL) from None
    except SessionNotInProgressError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=SESSION_NOT_IN_PROGRESS_DETAIL,
        ) from None
    except OutOfTurnError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=OUT_OF_TURN_DETAIL) from None
    except WordAlreadyRevealedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=WORD_ALREADY_REVEALED_DETAIL,
        ) from None
    except WordLockedError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=WORD_LOCKED_DETAIL) from None

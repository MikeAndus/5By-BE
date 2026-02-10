import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.create_session import CreateSessionRequest
from app.schemas.session_snapshot import SessionSnapshot
from app.services.session_create import GridsUnavailableError, create_session
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

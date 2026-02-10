import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.session_snapshot import SessionSnapshot
from app.services.session_snapshot import SessionSnapshotNotFoundError, load_session_snapshot

router = APIRouter(prefix="/sessions", tags=["sessions"])

SESSION_NOT_FOUND_DETAIL = {
    "code": "session_not_found",
    "message": "Session not found",
}


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

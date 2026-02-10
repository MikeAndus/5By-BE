from __future__ import annotations

import uuid
from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CellState, EventLog, Grid, Session, SessionStatus
from app.db.session import get_async_session
from app.schemas.sessions import CreateSessionRequest
from app.schemas.snapshot import SessionSnapshot, SnapshotLastEvent
from app.services.snapshot_serializer import serialize_session_snapshot

router = APIRouter(tags=["sessions"])


@dataclass(slots=True)
class SnapshotQueryData:
    session: Session
    grids_by_id: dict[UUID, Grid]
    cell_states: list[CellState]
    last_event: EventLog | None


@router.post("/sessions", response_model=SessionSnapshot, status_code=201)
async def create_session(
    payload: CreateSessionRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    async with db.begin():
        grids = await _select_two_random_grids(db)
        if len(grids) < 2:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Not enough grids seeded to create a session.",
            )

        session_id = uuid.uuid4()
        created_session = Session(
            session_id=session_id,
            player_1_id=uuid.uuid4(),
            player_2_id=uuid.uuid4(),
            player_1_name=payload.player_1_name,
            player_2_name=payload.player_2_name,
            player_1_grid_id=grids[0].grid_id,
            player_2_grid_id=grids[1].grid_id,
            current_turn=1,
            player_1_score=100,
            player_2_score=100,
            status=SessionStatus.IN_PROGRESS,
        )
        db.add(created_session)
        db.add_all(_build_initial_cell_states(session_id))

    snapshot_data = await _load_snapshot_query_data(db, session_id)
    if snapshot_data is None:
        raise HTTPException(status_code=500, detail="Session could not be loaded after creation.")

    snapshot = serialize_session_snapshot(
        snapshot_data.session,
        snapshot_data.grids_by_id,
        snapshot_data.cell_states,
        snapshot_data.last_event,
    )
    if snapshot_data.last_event is None:
        snapshot.last_event = SnapshotLastEvent(type="session_created", result="ok")

    return snapshot


@router.get("/sessions/{session_id}", response_model=SessionSnapshot)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> SessionSnapshot:
    snapshot_data = await _load_snapshot_query_data(db, session_id)
    if snapshot_data is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    return serialize_session_snapshot(
        snapshot_data.session,
        snapshot_data.grids_by_id,
        snapshot_data.cell_states,
        snapshot_data.last_event,
    )


async def _select_two_random_grids(db: AsyncSession) -> list[Grid]:
    grids_result = await db.execute(select(Grid).order_by(sa.func.random()).limit(2))
    return list(grids_result.scalars().all())


def _build_initial_cell_states(session_id: UUID) -> list[CellState]:
    return [
        CellState(
            session_id=session_id,
            player_id=player_id,
            cell_index=cell_index,
            revealed=False,
            locked=False,
            topics_used=[],
            revealed_by=None,
        )
        for player_id in (1, 2)
        for cell_index in range(25)
    ]


async def _load_snapshot_query_data(db: AsyncSession, session_id: UUID) -> SnapshotQueryData | None:
    session_result = await db.execute(select(Session).where(Session.session_id == session_id))
    session_row = session_result.scalar_one_or_none()
    if session_row is None:
        return None

    grids_result = await db.execute(
        select(Grid).where(Grid.grid_id.in_([session_row.player_1_grid_id, session_row.player_2_grid_id]))
    )
    grids = list(grids_result.scalars().all())
    grids_by_id = {grid.grid_id: grid for grid in grids}
    if session_row.player_1_grid_id not in grids_by_id or session_row.player_2_grid_id not in grids_by_id:
        raise HTTPException(status_code=500, detail="Session grid assignments are invalid.")

    cell_states_result = await db.execute(
        select(CellState)
        .where(CellState.session_id == session_id)
        .order_by(CellState.player_id.asc(), CellState.cell_index.asc())
    )
    cell_states = list(cell_states_result.scalars().all())

    event_result = await db.execute(
        select(EventLog)
        .where(EventLog.session_id == session_id)
        .order_by(
            EventLog.timestamp.desc(),
            EventLog.created_at.desc(),
            EventLog.event_id.desc(),
        )
        .limit(1)
    )
    last_event = event_result.scalar_one_or_none()

    return SnapshotQueryData(
        session=session_row,
        grids_by_id=grids_by_id,
        cell_states=cell_states,
        last_event=last_event,
    )

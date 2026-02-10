from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.snapshots import LastEventSnapshot, SessionSnapshot
from app.db.models.cell_state import CellState
from app.db.models.enums import SessionStatus as DbSessionStatus
from app.db.models.grid import Grid
from app.db.models.session import Session
from app.game.state_snapshot import build_state_snapshot

_SESSION_CREATED_EVENT = LastEventSnapshot(type="session_created", result="ok")


def _initial_session_status() -> DbSessionStatus:
    lobby_status = getattr(DbSessionStatus, "LOBBY", None)
    if isinstance(lobby_status, DbSessionStatus):
        return lobby_status
    return DbSessionStatus.IN_PROGRESS


async def _select_two_random_grids(db: AsyncSession) -> list[Grid]:
    grid_count_result = await db.execute(select(func.count(Grid.grid_id)))
    total_grids = int(grid_count_result.scalar_one())
    if total_grids < 2:
        return []

    grids_result = await db.execute(select(Grid).order_by(func.random()).limit(2))
    return list(grids_result.scalars().all())


async def create_session(
    db: AsyncSession,
    *,
    player_1_name: str | None = None,
    player_2_name: str | None = None,
) -> SessionSnapshot:
    grids = await _select_two_random_grids(db)
    if len(grids) < 2:
        raise HTTPException(
            status_code=503,
            detail="Not enough grids seeded to create a session.",
        )

    new_session = Session(
        player_1_id=uuid4(),
        player_2_id=uuid4(),
        player_1_name=player_1_name,
        player_2_name=player_2_name,
        player_1_grid_id=grids[0].grid_id,
        player_2_grid_id=grids[1].grid_id,
        current_turn=1,
        player_1_score=0,
        player_2_score=0,
        status=_initial_session_status(),
    )

    db.add(new_session)
    await db.flush()

    await db.execute(
        insert(CellState),
        [
            {
                "session_id": new_session.session_id,
                "player_id": player_id,
                "cell_index": cell_index,
            }
            for player_id in (1, 2)
            for cell_index in range(25)
        ],
    )
    await db.commit()

    return await build_state_snapshot(
        db,
        new_session.session_id,
        fallback_last_event=_SESSION_CREATED_EVENT,
    )


__all__ = ["create_session"]

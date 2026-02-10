from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cell_state import CellState
from app.db.models.grid import Grid
from app.db.models.session import Session


class GridsUnavailableError(Exception):
    pass


async def create_session(
    *,
    db: AsyncSession,
    player_1_name: str | None,
    player_2_name: str | None,
) -> uuid.UUID:
    async with db.begin():
        grid_ids = (await db.scalars(select(Grid.id).order_by(func.random()).limit(2))).all()
        if len(grid_ids) < 2:
            raise GridsUnavailableError("Not enough grids available to create a session")

        session = Session(
            player_1_grid_id=grid_ids[0],
            player_2_grid_id=grid_ids[1],
            player_1_name=player_1_name,
            player_2_name=player_2_name,
        )
        db.add(session)
        await db.flush()

        cell_states = [
            CellState(
                session_id=session.id,
                player_number=player_number,
                cell_index=cell_index,
                revealed=False,
                locked=False,
                letter=None,
                revealed_by=None,
                topics_used=[],
            )
            for player_number in (1, 2)
            for cell_index in range(25)
        ]
        db.add_all(cell_states)

    return session.id

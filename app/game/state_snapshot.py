from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiErrorCode, NotFoundError, RuleViolationError
from app.api.schemas.enums import SessionStatus as ApiSessionStatus
from app.api.schemas.snapshots import (
    CellSnapshot,
    LastEventSnapshot,
    PlayerSnapshot,
    SessionSnapshot,
)
from app.db.models.cell_state import CellState
from app.db.models.event_log import EventLog
from app.db.models.grid import Grid
from app.db.models.session import Session


def _cell_row_col(index: int) -> tuple[int, int]:
    return (index // 5, index % 5)


async def _load_session_or_404(db: AsyncSession, session_id: UUID) -> Session:
    session_result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = session_result.scalars().one_or_none()
    if session is None:
        raise NotFoundError(
            code=ApiErrorCode.SESSION_NOT_FOUND,
            details={"session_id": str(session_id)},
        )
    return session


def _build_last_event_snapshot(event: EventLog | None) -> LastEventSnapshot | None:
    if event is None:
        return None

    event_result = None
    message_to_speak = None
    if isinstance(event.event_data, dict):
        event_result = event.event_data.get("result")
        message_to_speak = event.event_data.get("message_to_speak")

    if event_result not in {"ok", "error"}:
        event_result = None

    return LastEventSnapshot(
        type=event.event_type.value,
        result=event_result,
        message_to_speak=message_to_speak,
    )


def _resolve_status(session: Session, session_id: UUID) -> ApiSessionStatus:
    try:
        return ApiSessionStatus(session.status.value)
    except ValueError as exc:
        raise RuleViolationError(
            code=ApiErrorCode.STATE_CORRUPT,
            details={
                "session_id": str(session_id),
                "rule": "unsupported_session_status",
                "status": session.status.value,
            },
        ) from exc


def _build_player_snapshots(
    session_id: UUID,
    session: Session,
    cell_states: list[CellState],
    grids_by_id: dict[UUID, Grid],
) -> list[PlayerSnapshot]:
    if len(cell_states) != 50:
        raise RuleViolationError(
            code=ApiErrorCode.STATE_CORRUPT,
            details={"session_id": str(session_id), "cell_state_count": len(cell_states)},
        )

    player_1_grid = grids_by_id.get(session.player_1_grid_id)
    player_2_grid = grids_by_id.get(session.player_2_grid_id)
    if player_1_grid is None or player_2_grid is None:
        raise RuleViolationError(
            code=ApiErrorCode.STATE_CORRUPT,
            details={
                "session_id": str(session_id),
                "player_1_grid_found": player_1_grid is not None,
                "player_2_grid_found": player_2_grid is not None,
            },
        )

    states_by_player: dict[int, dict[int, CellState]] = {1: {}, 2: {}}
    for state in cell_states:
        if state.player_id not in states_by_player:
            raise RuleViolationError(
                code=ApiErrorCode.STATE_CORRUPT,
                details={
                    "session_id": str(session_id),
                    "rule": "player_id_must_be_1_or_2",
                    "player_id": state.player_id,
                },
            )
        states_by_player[state.player_id][state.cell_index] = state

    players: list[PlayerSnapshot] = []
    for player_number, player_name, player_score, player_grid in (
        (1, session.player_1_name, session.player_1_score, player_1_grid),
        (2, session.player_2_name, session.player_2_score, player_2_grid),
    ):
        states = states_by_player[player_number]
        if len(states) != 25:
            raise RuleViolationError(
                code=ApiErrorCode.STATE_CORRUPT,
                details={
                    "session_id": str(session_id),
                    "player_id": player_number,
                    "cell_count": len(states),
                },
            )

        cells: list[CellSnapshot] = []
        for index in range(25):
            state = states.get(index)
            if state is None:
                raise RuleViolationError(
                    code=ApiErrorCode.STATE_CORRUPT,
                    details={
                        "session_id": str(session_id),
                        "player_id": player_number,
                        "missing_cell_index": index,
                    },
                )
            row, col = _cell_row_col(index)
            cells.append(
                CellSnapshot(
                    index=index,
                    row=row,
                    col=col,
                    revealed=state.revealed,
                    letter=player_grid.cells[index] if state.revealed else None,
                    locked=state.locked,
                    topics_used=list(state.topics_used or []),
                    revealed_by=(state.revealed_by.value if state.revealed_by else None),
                )
            )

        players.append(
            PlayerSnapshot(
                player_number=player_number,
                name=player_name,
                score=player_score,
                grid_id=player_grid.grid_id,
                cells=cells,
                completed=all(cell.revealed for cell in cells),
            )
        )

    return players


async def build_state_snapshot(
    db: AsyncSession,
    session_id: UUID,
    *,
    fallback_last_event: LastEventSnapshot | None = None,
) -> SessionSnapshot:
    session = await _load_session_or_404(db, session_id)

    cell_states_result = await db.execute(
        select(CellState).where(CellState.session_id == session_id)
    )
    cell_states = list(cell_states_result.scalars().all())

    grids_result = await db.execute(
        select(Grid).where(Grid.grid_id.in_([session.player_1_grid_id, session.player_2_grid_id]))
    )
    grids_by_id = {grid.grid_id: grid for grid in grids_result.scalars().all()}

    last_event_result = await db.execute(
        select(EventLog)
        .where(EventLog.session_id == session_id)
        .order_by(desc(EventLog.timestamp), desc(EventLog.created_at))
        .limit(1)
    )
    last_event = last_event_result.scalars().one_or_none()

    return SessionSnapshot(
        session_id=session.session_id,
        status=_resolve_status(session, session_id),
        current_turn=session.current_turn,
        players=_build_player_snapshots(session_id, session, cell_states, grids_by_id),
        last_event=_build_last_event_snapshot(last_event) or fallback_last_event,
    )


__all__ = ["build_state_snapshot"]

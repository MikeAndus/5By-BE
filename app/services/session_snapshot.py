from __future__ import annotations

from typing import Sequence
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CANONICAL_TOPICS
from app.db.models.cell_state import CellState
from app.db.models.event_log import EventLog
from app.db.models.session import Session
from app.schemas.enums import EventType, RevealedBy, SessionStatus, Topic
from app.schemas.session_snapshot import CellSnapshot, LastEvent, PlayerSnapshot, SessionSnapshot

logger = logging.getLogger(__name__)


class SessionSnapshotNotFoundError(Exception):
    def __init__(self, session_id: uuid.UUID) -> None:
        super().__init__(f"Session {session_id} not found")
        self.session_id = session_id


_CANONICAL_TOPICS = [Topic(topic) for topic in CANONICAL_TOPICS]


def _to_session_status(value: object) -> SessionStatus:
    if isinstance(value, SessionStatus):
        return value

    raw = getattr(value, "value", value)
    return SessionStatus(str(raw))


def _to_revealed_by(value: object | None) -> RevealedBy | None:
    if value is None:
        return None

    if isinstance(value, RevealedBy):
        return value

    raw = getattr(value, "value", value)
    return RevealedBy(str(raw))


def _to_event_type(value: object) -> EventType:
    if isinstance(value, EventType):
        return value

    raw = getattr(value, "value", value)
    return EventType(str(raw))


def _build_cell_snapshots(rows: Sequence[CellState]) -> list[CellSnapshot]:
    return [
        CellSnapshot(
            index=row.cell_index,
            row=row.cell_index // 5,
            col=row.cell_index % 5,
            revealed=row.revealed,
            locked=row.locked,
            letter=row.letter,
            revealed_by=_to_revealed_by(row.revealed_by),
            topics=_CANONICAL_TOPICS,
        )
        for row in rows
    ]


async def _build_player_snapshot(
    *,
    session: Session,
    player_number: int,
    db: AsyncSession,
) -> PlayerSnapshot:
    rows = (
        await db.scalars(
            select(CellState)
            .where(
                CellState.session_id == session.id,
                CellState.player_number == player_number,
            )
            .order_by(CellState.cell_index.asc())
        )
    ).all()

    if len(rows) == 25:
        cells = _build_cell_snapshots(rows)
        completed = all(cell.revealed for cell in rows)
    elif len(rows) == 0:
        cells = []
        completed = False
    else:
        logger.warning(
            "Session %s player %s has %s cell_states rows; returning empty cells for Phase 1 stability",
            session.id,
            player_number,
            len(rows),
        )
        cells = []
        completed = False

    if player_number == 1:
        name = session.player_1_name
        score = session.player_1_score
        grid_id = session.player_1_grid_id
    else:
        name = session.player_2_name
        score = session.player_2_score
        grid_id = session.player_2_grid_id

    return PlayerSnapshot(
        player_number=player_number,
        name=name,
        score=score,
        grid_id=grid_id,
        completed=completed,
        cells=cells,
    )


async def load_session_snapshot(session_id: uuid.UUID, db: AsyncSession) -> SessionSnapshot:
    session = await db.scalar(select(Session).where(Session.id == session_id))
    if session is None:
        raise SessionSnapshotNotFoundError(session_id)

    player_1 = await _build_player_snapshot(session=session, player_number=1, db=db)
    player_2 = await _build_player_snapshot(session=session, player_number=2, db=db)

    latest_event = await db.scalar(
        select(EventLog)
        .where(EventLog.session_id == session.id)
        .order_by(EventLog.created_at.desc(), EventLog.id.desc())
        .limit(1)
    )

    last_event = (
        LastEvent(
            type=_to_event_type(latest_event.type),
            event_data=latest_event.event_data,
            created_at=latest_event.created_at,
        )
        if latest_event is not None
        else None
    )

    return SessionSnapshot(
        session_id=session.id,
        status=_to_session_status(session.status),
        current_turn=session.current_turn,
        players=[player_1, player_2],
        last_event=last_event,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )

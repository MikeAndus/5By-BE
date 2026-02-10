from __future__ import annotations

from uuid import UUID

from app.db.models import CellState, EventLog, Grid, Session
from app.schemas.snapshot import (
    SessionCellSnapshot,
    SessionPlayerSnapshot,
    SessionSnapshot,
    SnapshotLastEvent,
)


def serialize_session_snapshot(
    session: Session,
    grids_by_id: dict[UUID, Grid],
    cell_states: list[CellState],
    last_event: EventLog | None,
    *,
    include_hidden_letters: bool = False,
) -> SessionSnapshot:
    player_cells_by_index = _map_cell_states_by_player_and_index(cell_states)

    player_1_grid = grids_by_id[session.player_1_grid_id]
    player_2_grid = grids_by_id[session.player_2_grid_id]

    player_1_cells = _serialize_player_cells(
        player_cells_by_index=player_cells_by_index[1],
        grid=player_1_grid,
        include_hidden_letters=include_hidden_letters,
    )
    player_2_cells = _serialize_player_cells(
        player_cells_by_index=player_cells_by_index[2],
        grid=player_2_grid,
        include_hidden_letters=include_hidden_letters,
    )

    payload = SessionSnapshot(
        session_id=session.session_id,
        status=session.status.value,
        current_turn=session.current_turn,
        players=[
            SessionPlayerSnapshot(
                player_number=1,
                name=session.player_1_name,
                score=session.player_1_score,
                grid_id=session.player_1_grid_id,
                cells=player_1_cells,
                completed=all(cell.revealed for cell in player_1_cells),
            ),
            SessionPlayerSnapshot(
                player_number=2,
                name=session.player_2_name,
                score=session.player_2_score,
                grid_id=session.player_2_grid_id,
                cells=player_2_cells,
                completed=all(cell.revealed for cell in player_2_cells),
            ),
        ],
        last_event=_serialize_last_event(last_event),
    )
    return payload


def _serialize_last_event(last_event: EventLog | None) -> SnapshotLastEvent:
    if last_event is None:
        return SnapshotLastEvent(type="none")

    event_payload: dict[str, str] = {"type": last_event.event_type.value}
    if isinstance(last_event.event_data, dict):
        result = last_event.event_data.get("result")
        if result is not None:
            event_payload["result"] = str(result)

        message_to_speak = last_event.event_data.get("message_to_speak")
        if message_to_speak is not None:
            event_payload["message_to_speak"] = str(message_to_speak)

    return SnapshotLastEvent.model_validate(event_payload)


def _map_cell_states_by_player_and_index(
    cell_states: list[CellState],
) -> dict[int, dict[int, CellState]]:
    result: dict[int, dict[int, CellState]] = {1: {}, 2: {}}
    for state in cell_states:
        if state.player_id in (1, 2) and 0 <= state.cell_index <= 24:
            result[state.player_id][state.cell_index] = state
    return result


def _serialize_player_cells(
    *,
    player_cells_by_index: dict[int, CellState],
    grid: Grid,
    include_hidden_letters: bool,
) -> list[SessionCellSnapshot]:
    cells: list[SessionCellSnapshot] = []
    for index in range(25):
        state = player_cells_by_index.get(index)
        revealed = bool(state.revealed) if state is not None else False
        letter = grid.cells[index] if include_hidden_letters or revealed else None
        revealed_by = state.revealed_by.value if state is not None and state.revealed_by is not None else None

        cells.append(
            SessionCellSnapshot(
                index=index,
                row=index // 5,
                col=index % 5,
                revealed=revealed,
                letter=letter,
                locked=bool(state.locked) if state is not None else False,
                topics_used=list(state.topics_used or []) if state is not None else [],
                revealed_by=revealed_by,
            )
        )

    return cells


__all__ = ["serialize_session_snapshot"]

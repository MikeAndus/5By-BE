from __future__ import annotations

GRID_SIDE_LENGTH = 5
GRID_CELL_COUNT = GRID_SIDE_LENGTH * GRID_SIDE_LENGTH


def cell_index_from_row_col(row: int, col: int) -> int:
    if not (0 <= row < GRID_SIDE_LENGTH):
        raise ValueError("row must be between 0 and 4")
    if not (0 <= col < GRID_SIDE_LENGTH):
        raise ValueError("col must be between 0 and 4")
    return (row * GRID_SIDE_LENGTH) + col


def row_col_from_cell_index(cell_index: int) -> tuple[int, int]:
    if not (0 <= cell_index < GRID_CELL_COUNT):
        raise ValueError("cell_index must be between 0 and 24")
    return divmod(cell_index, GRID_SIDE_LENGTH)


def line_cell_indexes(direction: str, index: int) -> list[int]:
    if not (0 <= index < GRID_SIDE_LENGTH):
        raise ValueError("index must be between 0 and 4")

    if direction == "across":
        return [cell_index_from_row_col(index, col) for col in range(GRID_SIDE_LENGTH)]
    if direction == "down":
        return [cell_index_from_row_col(row, index) for row in range(GRID_SIDE_LENGTH)]
    raise ValueError("direction must be either 'across' or 'down'")


__all__ = [
    "GRID_CELL_COUNT",
    "GRID_SIDE_LENGTH",
    "cell_index_from_row_col",
    "line_cell_indexes",
    "row_col_from_cell_index",
]

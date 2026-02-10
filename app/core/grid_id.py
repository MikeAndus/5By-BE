from __future__ import annotations

from uuid import UUID, uuid5

GRID_NAMESPACE_UUID = UUID("129f7541-7655-4635-85bf-994f54ec2807")


def derive_grid_id(cells: str, words_across: list[str], words_down: list[str]) -> UUID:
    payload = f"{cells}|{'/'.join(words_across)}|{'/'.join(words_down)}"
    return uuid5(GRID_NAMESPACE_UUID, payload)


__all__ = ["GRID_NAMESPACE_UUID", "derive_grid_id"]

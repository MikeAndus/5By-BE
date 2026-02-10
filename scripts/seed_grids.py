"""Seed the `grids` table from a local JSON array or JSONL file.

Accepted row shape:
{"cells": "<25 uppercase letters>", "words_across": ["..." x5], "words_down": ["..." x5]}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.models.grid import Grid
from app.db.session import normalize_database_url

CELLS_PATTERN = re.compile(r"^[A-Z]{25}$")


class GridValidationError(ValueError):
    pass


def _validate_words(*, key: str, value: Any, row_number: int) -> list[str]:
    if not isinstance(value, list):
        raise GridValidationError(f"row {row_number}: {key} must be an array")
    if len(value) != 5:
        raise GridValidationError(f"row {row_number}: {key} must contain exactly 5 entries")
    if not all(isinstance(item, str) for item in value):
        raise GridValidationError(f"row {row_number}: {key} entries must all be strings")
    return [item.strip() for item in value]


def _validate_row(raw_row: Any, row_number: int) -> dict[str, Any]:
    if not isinstance(raw_row, dict):
        raise GridValidationError(f"row {row_number}: expected object")

    cells = raw_row.get("cells")
    if not isinstance(cells, str):
        raise GridValidationError(f"row {row_number}: cells must be a string")

    cells = cells.strip()
    if len(cells) != 25:
        raise GridValidationError(f"row {row_number}: cells must be length 25")
    if not CELLS_PATTERN.fullmatch(cells):
        raise GridValidationError(f"row {row_number}: cells must contain uppercase letters A-Z only")

    words_across = _validate_words(key="words_across", value=raw_row.get("words_across"), row_number=row_number)
    words_down = _validate_words(key="words_down", value=raw_row.get("words_down"), row_number=row_number)

    return {
        "cells": cells,
        "words_across": words_across,
        "words_down": words_down,
    }


def _load_json_array(path: Path) -> list[Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GridValidationError(f"invalid JSON array file: {exc}") from exc

    if not isinstance(payload, list):
        raise GridValidationError("JSON file must contain a top-level array")

    return payload


def _load_jsonl(path: Path) -> list[Any]:
    rows: list[Any] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise GridValidationError(f"line {line_number}: invalid JSON object ({exc})") from exc
    return rows


def load_and_validate_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise GridValidationError(f"file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        raw_rows = _load_jsonl(path)
    else:
        raw_rows = _load_json_array(path)

    return [_validate_row(row, index) for index, row in enumerate(raw_rows, start=1)]


async def seed_grids(database_url: str, rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    attempted = len(rows)
    if attempted == 0:
        return 0, 0, 0

    engine = create_async_engine(normalize_database_url(database_url), pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            stmt = (
                pg_insert(Grid.__table__)
                .values(rows)
                .on_conflict_do_nothing(index_elements=[Grid.__table__.c.cells])
                .returning(Grid.__table__.c.id)
            )
            result = await connection.execute(stmt)
            inserted = len(result.scalars().all())
    finally:
        await engine.dispose()

    skipped = attempted - inserted
    return attempted, inserted, skipped


async def async_main(path: Path) -> int:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required")

    rows = load_and_validate_rows(path)
    attempted, inserted, skipped = await seed_grids(settings.database_url, rows)
    print(f"attempted={attempted} inserted={inserted} skipped={skipped}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the grids table from a local file")
    parser.add_argument("path", type=Path, help="Path to .json (array) or .jsonl file")
    args = parser.parse_args()

    try:
        return asyncio.run(async_main(args.path))
    except (GridValidationError, RuntimeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

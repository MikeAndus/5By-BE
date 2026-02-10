from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.core.grid_validation import ValidationIssue, validate_grid_seed_payload
from app.core.logging import configure_logging
from app.db.models.grid import Grid
from app.db.session import get_async_sessionmaker

logger = structlog.get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and seed immutable grids into PostgreSQL")
    parser.add_argument("--data", default="app/data/grids.json", help="Path to grids JSON file")
    parser.add_argument("--limit", type=_positive_int, default=None, help="Seed only the first N valid records")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report counts without DB writes")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Skip invalid records and continue seeding valid records",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level",
    )
    return parser


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("limit must be a positive integer")
    return parsed


async def run(args: argparse.Namespace) -> int:
    configure_logging(args.log_level)

    data_path = Path(args.data)
    payload = _load_payload(data_path)
    if payload is None:
        return 1

    validation_result = validate_grid_seed_payload(payload)
    total_records = len(payload) if isinstance(payload, list) else 0

    for issue in validation_result.issues:
        _log_validation_issue(issue)

    valid_records = validation_result.valid_records
    limited_records = valid_records[: args.limit] if args.limit else valid_records

    if args.dry_run:
        _log_summary(
            total_records=total_records,
            valid_count=len(valid_records),
            invalid_count=validation_result.invalid_count,
            inserted_count=0,
            skipped_count=0,
            dry_run=True,
            limit=args.limit,
        )
        return 1 if validation_result.invalid_count > 0 else 0

    if validation_result.invalid_count > 0 and not args.continue_on_error:
        _log_summary(
            total_records=total_records,
            valid_count=len(valid_records),
            invalid_count=validation_result.invalid_count,
            inserted_count=0,
            skipped_count=0,
            dry_run=False,
            limit=args.limit,
        )
        logger.error(
            "grid_seed_aborted",
            reason="validation_failed",
            invalid_count=validation_result.invalid_count,
            continue_on_error=False,
        )
        return 1

    inserted_count = 0
    skipped_count = 0
    session_factory = get_async_sessionmaker()

    try:
        async with session_factory() as session:
            async with session.begin():
                for record in limited_records:
                    stmt = (
                        insert(Grid)
                        .values(
                            grid_id=record.grid_id,
                            cells=record.cells,
                            words_across=record.words_across,
                            words_down=record.words_down,
                        )
                        .on_conflict_do_nothing(index_elements=["grid_id"])
                        .returning(Grid.grid_id)
                    )
                    result = await session.execute(stmt)
                    inserted_grid_id = result.scalar_one_or_none()
                    if inserted_grid_id is None:
                        skipped_count += 1
                    else:
                        inserted_count += 1
    except IntegrityError as exc:
        error_message = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
        logger.error("grid_seed_integrity_error", error=error_message)
        if "uq_grids_cells" in error_message or "grids_cells_key" in error_message:
            logger.error(
                "grid_seed_cells_collision",
                reason="unique_cells_violation",
                detail="Detected conflicting rows with the same cells but different payload-derived grid IDs",
            )
        return 1

    _log_summary(
        total_records=total_records,
        valid_count=len(valid_records),
        invalid_count=validation_result.invalid_count,
        inserted_count=inserted_count,
        skipped_count=skipped_count,
        dry_run=False,
        limit=args.limit,
    )

    if validation_result.invalid_count > 0:
        logger.error(
            "grid_seed_completed_with_errors",
            invalid_count=validation_result.invalid_count,
            continue_on_error=True,
        )
        return 1

    return 0


def _load_payload(path: Path) -> Any | None:
    try:
        with path.open("r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except FileNotFoundError:
        logger.error("grid_seed_data_file_missing", data_path=str(path))
    except json.JSONDecodeError as exc:
        logger.error(
            "grid_seed_invalid_json",
            data_path=str(path),
            line=exc.lineno,
            column=exc.colno,
            message=exc.msg,
        )

    return None


def _log_validation_issue(issue: ValidationIssue) -> None:
    event_payload: dict[str, Any] = {
        "row_index": issue.row_index,
        "reason": issue.reason,
    }
    if issue.value is not None:
        event_payload["value"] = issue.value

    logger.error("grid_seed_validation_error", **event_payload)


def _log_summary(
    *,
    total_records: int,
    valid_count: int,
    invalid_count: int,
    inserted_count: int,
    skipped_count: int,
    dry_run: bool,
    limit: int | None,
) -> None:
    logger.info(
        "grid_seed_summary",
        total_records=total_records,
        valid_count=valid_count,
        invalid_count=invalid_count,
        inserted_count=inserted_count,
        skipped_count=skipped_count,
        dry_run=dry_run,
        limit=limit,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())

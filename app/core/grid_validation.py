from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from app.core.grid_id import derive_grid_id

GRID_SIZE = 5
CELL_COUNT = GRID_SIZE * GRID_SIZE
EXPECTED_KEYS = {"cells", "words_across", "words_down"}
WORD_PATTERN = re.compile(r"^[A-Z]{5}$")
CELLS_PATTERN = re.compile(r"^[A-Z]{25}$")


@dataclass(frozen=True)
class ValidationIssue:
    row_index: int
    reason: str
    value: str | None = None


@dataclass(frozen=True)
class GridSeedRecord:
    grid_id: UUID
    cells: str
    words_across: list[str]
    words_down: list[str]


@dataclass(frozen=True)
class GridValidationResult:
    valid_records: list[GridSeedRecord]
    issues: list[ValidationIssue]

    @property
    def invalid_count(self) -> int:
        invalid_rows = {issue.row_index for issue in self.issues if issue.row_index >= 0}
        if invalid_rows:
            return len(invalid_rows)
        return len(self.issues)


def validate_grid_seed_payload(payload: object) -> GridValidationResult:
    if not isinstance(payload, list):
        return GridValidationResult(
            valid_records=[],
            issues=[ValidationIssue(row_index=-1, reason="invalid_top_level_type", value=type(payload).__name__)],
        )

    valid_records: list[GridSeedRecord] = []
    issues: list[ValidationIssue] = []
    seen_cells: dict[str, int] = {}
    seen_grid_ids: dict[UUID, int] = {}

    for row_index, raw_record in enumerate(payload):
        normalized_record, record_issues = _validate_record(raw_record, row_index=row_index)
        if record_issues:
            issues.extend(record_issues)
            continue

        assert normalized_record is not None

        if normalized_record.cells in seen_cells:
            issues.append(
                ValidationIssue(
                    row_index=row_index,
                    reason="duplicate_cells_in_file",
                    value=_truncate(normalized_record.cells),
                )
            )
            continue

        grid_id = derive_grid_id(
            normalized_record.cells,
            normalized_record.words_across,
            normalized_record.words_down,
        )

        if grid_id in seen_grid_ids:
            issues.append(
                ValidationIssue(
                    row_index=row_index,
                    reason="duplicate_grid_id_in_file",
                    value=str(grid_id),
                )
            )
            continue

        seen_cells[normalized_record.cells] = row_index
        seen_grid_ids[grid_id] = row_index

        valid_records.append(
            GridSeedRecord(
                grid_id=grid_id,
                cells=normalized_record.cells,
                words_across=normalized_record.words_across,
                words_down=normalized_record.words_down,
            )
        )

    return GridValidationResult(valid_records=valid_records, issues=issues)


@dataclass(frozen=True)
class _NormalizedRecord:
    cells: str
    words_across: list[str]
    words_down: list[str]


def _validate_record(raw_record: object, row_index: int) -> tuple[_NormalizedRecord | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []

    if not isinstance(raw_record, dict):
        return None, [ValidationIssue(row_index=row_index, reason="record_type", value=type(raw_record).__name__)]

    missing_keys = sorted(EXPECTED_KEYS - set(raw_record.keys()))
    extra_keys = sorted(set(raw_record.keys()) - EXPECTED_KEYS)

    if missing_keys:
        issues.append(
            ValidationIssue(
                row_index=row_index,
                reason="missing_keys",
                value=",".join(missing_keys),
            )
        )
    if extra_keys:
        issues.append(
            ValidationIssue(
                row_index=row_index,
                reason="unexpected_keys",
                value=",".join(extra_keys),
            )
        )

    if issues:
        return None, issues

    cells_value = raw_record["cells"]
    if not isinstance(cells_value, str):
        issues.append(ValidationIssue(row_index=row_index, reason="cells_type", value=type(cells_value).__name__))
        return None, issues

    words_across = _normalize_words(raw_record["words_across"], row_index, "words_across")
    words_down = _normalize_words(raw_record["words_down"], row_index, "words_down")

    issues.extend(words_across.issues)
    issues.extend(words_down.issues)

    normalized_cells = cells_value.strip().upper()
    if len(normalized_cells) != CELL_COUNT:
        issues.append(
            ValidationIssue(
                row_index=row_index,
                reason="cells_length",
                value=str(len(normalized_cells)),
            )
        )
    elif not CELLS_PATTERN.match(normalized_cells):
        issues.append(
            ValidationIssue(
                row_index=row_index,
                reason="invalid_charset",
                value=_truncate(normalized_cells),
            )
        )

    if issues:
        return None, issues

    assert words_across.values is not None
    assert words_down.values is not None

    for row in range(GRID_SIZE):
        expected = normalized_cells[row * GRID_SIZE : (row + 1) * GRID_SIZE]
        if words_across.values[row] != expected:
            issues.append(
                ValidationIssue(
                    row_index=row_index,
                    reason=f"across_mismatch_row_{row + 1}",
                    value=words_across.values[row],
                )
            )

    for column in range(GRID_SIZE):
        expected = "".join(normalized_cells[row * GRID_SIZE + column] for row in range(GRID_SIZE))
        if words_down.values[column] != expected:
            issues.append(
                ValidationIssue(
                    row_index=row_index,
                    reason=f"down_mismatch_col_{column + 1}",
                    value=words_down.values[column],
                )
            )

    if issues:
        return None, issues

    return _NormalizedRecord(
        cells=normalized_cells,
        words_across=words_across.values,
        words_down=words_down.values,
    ), []


@dataclass(frozen=True)
class _WordNormalizationResult:
    values: list[str] | None
    issues: list[ValidationIssue]


def _normalize_words(raw_words: object, row_index: int, field_name: str) -> _WordNormalizationResult:
    issues: list[ValidationIssue] = []

    if not isinstance(raw_words, list):
        return _WordNormalizationResult(
            values=None,
            issues=[ValidationIssue(row_index=row_index, reason=f"{field_name}_type", value=type(raw_words).__name__)],
        )

    if len(raw_words) != GRID_SIZE:
        return _WordNormalizationResult(
            values=None,
            issues=[ValidationIssue(row_index=row_index, reason=f"{field_name}_length", value=str(len(raw_words)))],
        )

    normalized_words: list[str] = []
    for index, raw_word in enumerate(raw_words):
        if not isinstance(raw_word, str):
            issues.append(
                ValidationIssue(
                    row_index=row_index,
                    reason=f"{field_name}_item_type_{index + 1}",
                    value=type(raw_word).__name__,
                )
            )
            continue

        normalized_word = raw_word.strip().upper()
        if not WORD_PATTERN.match(normalized_word):
            issues.append(
                ValidationIssue(
                    row_index=row_index,
                    reason=f"{field_name}_invalid_word_{index + 1}",
                    value=_truncate(normalized_word),
                )
            )
            continue

        normalized_words.append(normalized_word)

    if issues:
        return _WordNormalizationResult(values=None, issues=issues)

    return _WordNormalizationResult(values=normalized_words, issues=[])


def _truncate(value: str, max_length: int = 40) -> str:
    if len(value) <= max_length:
        return value

    return f"{value[: max_length - 3]}..."


__all__ = [
    "GridSeedRecord",
    "GridValidationResult",
    "ValidationIssue",
    "validate_grid_seed_payload",
]

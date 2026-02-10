"""grid constraints and uniqueness

Revision ID: 20260210_be1_2
Revises: 20260210_be1
Create Date: 2026-02-10 08:40:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260210_be1_2"
down_revision: Union[str, None] = "20260210_be1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not _has_table("grids"):
        op.create_table(
            "grids",
            sa.Column("grid_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("cells", sa.String(length=25), nullable=False),
            sa.Column("words_across", postgresql.ARRAY(sa.TEXT()), nullable=False),
            sa.Column("words_down", postgresql.ARRAY(sa.TEXT()), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint("length(cells) = 25", name="ck_grids_cells_len"),
            sa.CheckConstraint("cells ~ '^[A-Z]{25}$'", name="ck_grids_cells_charset"),
            sa.CheckConstraint("array_length(words_across, 1) = 5", name="ck_grids_words_across_len"),
            sa.CheckConstraint("array_length(words_down, 1) = 5", name="ck_grids_words_down_len"),
            sa.PrimaryKeyConstraint("grid_id"),
            sa.UniqueConstraint("cells", name="uq_grids_cells"),
        )
        return

    _ensure_column_shapes()
    _ensure_constraints()


def downgrade() -> None:
    if not _has_table("grids"):
        return

    if _has_constraint("grids", "uq_grids_cells", constraint_type="unique"):
        op.drop_constraint("uq_grids_cells", "grids", type_="unique")

    if _has_constraint("grids", "ck_grids_cells_charset", constraint_type="check"):
        op.drop_constraint("ck_grids_cells_charset", "grids", type_="check")

    if _has_constraint("grids", "ck_grids_cells_len", constraint_type="check"):
        op.drop_constraint("ck_grids_cells_len", "grids", type_="check")

    columns = {column["name"]: column for column in _inspector().get_columns("grids")}
    cells_column = columns.get("cells")
    if cells_column is not None and not isinstance(cells_column["type"], postgresql.ARRAY):
        op.alter_column(
            "grids",
            "cells",
            existing_type=cells_column["type"],
            type_=postgresql.ARRAY(sa.CHAR(length=1)),
            existing_nullable=False,
            postgresql_using="string_to_array(cells, NULL)::char(1)[]",
        )

    if not _has_constraint("grids", "ck_grids_cells_len", constraint_type="check"):
        op.create_check_constraint("ck_grids_cells_len", "grids", "array_length(cells, 1) = 25")


def _ensure_column_shapes() -> None:
    columns = {column["name"]: column for column in _inspector().get_columns("grids")}

    if "cells" not in columns:
        op.add_column(
            "grids",
            sa.Column(
                "cells",
                sa.String(length=25),
                nullable=False,
                server_default=sa.text("'AAAAAAAAAAAAAAAAAAAAAAAAA'"),
            ),
        )
        op.alter_column("grids", "cells", server_default=None)
    else:
        cells_column = columns["cells"]
        if isinstance(cells_column["type"], postgresql.ARRAY):
            if _has_constraint("grids", "ck_grids_cells_len", constraint_type="check"):
                op.drop_constraint("ck_grids_cells_len", "grids", type_="check")

            op.alter_column(
                "grids",
                "cells",
                existing_type=cells_column["type"],
                type_=sa.String(length=25),
                existing_nullable=False,
                postgresql_using="array_to_string(cells, '')",
            )
        elif not isinstance(cells_column["type"], sa.String):
            op.alter_column(
                "grids",
                "cells",
                existing_type=cells_column["type"],
                type_=sa.String(length=25),
                existing_nullable=False,
                postgresql_using="cells::varchar(25)",
            )
        elif getattr(cells_column["type"], "length", None) != 25:
            op.alter_column(
                "grids",
                "cells",
                existing_type=cells_column["type"],
                type_=sa.String(length=25),
                existing_nullable=False,
            )

    if "words_across" not in columns:
        op.add_column(
            "grids",
            sa.Column(
                "words_across",
                postgresql.ARRAY(sa.TEXT()),
                nullable=False,
                server_default=sa.text("ARRAY['AAAAA','AAAAA','AAAAA','AAAAA','AAAAA']::text[]"),
            ),
        )
        op.alter_column("grids", "words_across", server_default=None)

    if "words_down" not in columns:
        op.add_column(
            "grids",
            sa.Column(
                "words_down",
                postgresql.ARRAY(sa.TEXT()),
                nullable=False,
                server_default=sa.text("ARRAY['AAAAA','AAAAA','AAAAA','AAAAA','AAAAA']::text[]"),
            ),
        )
        op.alter_column("grids", "words_down", server_default=None)


def _ensure_constraints() -> None:
    if _has_constraint("grids", "ck_grids_cells_len", constraint_type="check"):
        op.drop_constraint("ck_grids_cells_len", "grids", type_="check")

    op.create_check_constraint("ck_grids_cells_len", "grids", "length(cells) = 25")

    if not _has_constraint("grids", "ck_grids_cells_charset", constraint_type="check"):
        op.create_check_constraint("ck_grids_cells_charset", "grids", "cells ~ '^[A-Z]{25}$'")

    if not _has_constraint("grids", "ck_grids_words_across_len", constraint_type="check"):
        op.create_check_constraint("ck_grids_words_across_len", "grids", "array_length(words_across, 1) = 5")

    if not _has_constraint("grids", "ck_grids_words_down_len", constraint_type="check"):
        op.create_check_constraint("ck_grids_words_down_len", "grids", "array_length(words_down, 1) = 5")

    if not _has_unique_on_cells():
        op.create_unique_constraint("uq_grids_cells", "grids", ["cells"])


def _has_unique_on_cells() -> bool:
    inspector = _inspector()
    for unique_constraint in inspector.get_unique_constraints("grids"):
        columns = unique_constraint.get("column_names") or []
        if list(columns) == ["cells"]:
            return True

    for index in inspector.get_indexes("grids"):
        columns = index.get("column_names") or []
        if bool(index.get("unique")) and list(columns) == ["cells"]:
            return True

    return False


def _has_constraint(table_name: str, constraint_name: str, constraint_type: str) -> bool:
    inspector = _inspector()

    if constraint_type == "check":
        return any(
            check_constraint.get("name") == constraint_name
            for check_constraint in inspector.get_check_constraints(table_name)
        )

    if constraint_type == "unique":
        return any(
            unique_constraint.get("name") == constraint_name
            for unique_constraint in inspector.get_unique_constraints(table_name)
        )

    raise ValueError(f"Unsupported constraint type: {constraint_type}")


def _has_table(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())

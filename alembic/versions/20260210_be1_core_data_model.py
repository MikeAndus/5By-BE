"""core data model

Revision ID: 20260210_be1
Revises: 
Create Date: 2026-02-10 08:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260210_be1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    session_status_enum = postgresql.ENUM(
        "in_progress",
        "complete",
        name="session_status",
        create_type=False,
    )
    revealed_by_enum = postgresql.ENUM(
        "question",
        "guess",
        "auto",
        name="revealed_by",
        create_type=False,
    )
    event_type_enum = postgresql.ENUM(
        "question_asked",
        "question_answered",
        "letter_guessed",
        "word_guessed",
        name="event_type",
        create_type=False,
    )

    bind = op.get_bind()
    session_status_enum.create(bind, checkfirst=True)
    revealed_by_enum.create(bind, checkfirst=True)
    event_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "grids",
        sa.Column("grid_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cells", postgresql.ARRAY(sa.CHAR(length=1)), nullable=False),
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
        sa.CheckConstraint("array_length(cells, 1) = 25", name="ck_grids_cells_len"),
        sa.CheckConstraint("array_length(words_across, 1) = 5", name="ck_grids_words_across_len"),
        sa.CheckConstraint("array_length(words_down, 1) = 5", name="ck_grids_words_down_len"),
        sa.PrimaryKeyConstraint("grid_id"),
    )

    op.create_table(
        "sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_1_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_2_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_1_name", sa.String(length=30), nullable=True),
        sa.Column("player_2_name", sa.String(length=30), nullable=True),
        sa.Column("player_1_grid_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_2_grid_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_turn", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("player_1_score", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("player_2_score", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column(
            "status",
            session_status_enum,
            nullable=False,
            server_default=sa.text("'in_progress'::session_status"),
        ),
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
        sa.CheckConstraint("current_turn IN (1, 2)", name="ck_sessions_current_turn"),
        sa.ForeignKeyConstraint(["player_1_grid_id"], ["grids.grid_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["player_2_grid_id"], ["grids.grid_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("session_id"),
    )

    op.create_table(
        "cell_states",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", sa.SmallInteger(), nullable=False),
        sa.Column("cell_index", sa.SmallInteger(), nullable=False),
        sa.Column("revealed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "topics_used",
            postgresql.ARRAY(sa.TEXT()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("revealed_by", revealed_by_enum, nullable=True),
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
        sa.CheckConstraint("player_id IN (1, 2)", name="ck_cell_states_player_id"),
        sa.CheckConstraint("cell_index BETWEEN 0 AND 24", name="ck_cell_states_cell_index"),
        sa.CheckConstraint(
            "array_length(topics_used, 1) IS NULL OR array_length(topics_used, 1) <= 5",
            name="ck_cell_states_topics_used_max_len",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id", "player_id", "cell_index"),
    )

    op.create_table(
        "event_logs",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", sa.SmallInteger(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("event_type", event_type_enum, nullable=False),
        sa.Column("event_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
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
        sa.CheckConstraint("player_id IN (1, 2)", name="ck_event_logs_player_id"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )

    op.create_index("ix_sessions_status", "sessions", ["status"], unique=False)
    op.create_index("ix_sessions_updated_at", "sessions", ["updated_at"], unique=False)
    op.create_index("cell_states_session_player_idx", "cell_states", ["session_id", "player_id"], unique=False)
    op.create_index("cell_states_session_idx", "cell_states", ["session_id"], unique=False)
    op.create_index("event_logs_session_timestamp_idx", "event_logs", ["session_id", "timestamp"], unique=False)
    op.create_index("event_logs_session_event_type_idx", "event_logs", ["session_id", "event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("event_logs_session_event_type_idx", table_name="event_logs")
    op.drop_index("event_logs_session_timestamp_idx", table_name="event_logs")
    op.drop_index("cell_states_session_idx", table_name="cell_states")
    op.drop_index("cell_states_session_player_idx", table_name="cell_states")
    op.drop_index("ix_sessions_updated_at", table_name="sessions")
    op.drop_index("ix_sessions_status", table_name="sessions")

    op.drop_table("event_logs")
    op.drop_table("cell_states")
    op.drop_table("sessions")
    op.drop_table("grids")

    event_type_enum = postgresql.ENUM(
        "question_asked",
        "question_answered",
        "letter_guessed",
        "word_guessed",
        name="event_type",
        create_type=False,
    )
    revealed_by_enum = postgresql.ENUM("question", "guess", "auto", name="revealed_by", create_type=False)
    session_status_enum = postgresql.ENUM(
        "in_progress",
        "complete",
        name="session_status",
        create_type=False,
    )

    bind = op.get_bind()
    event_type_enum.drop(bind, checkfirst=True)
    revealed_by_enum.drop(bind, checkfirst=True)
    session_status_enum.drop(bind, checkfirst=True)

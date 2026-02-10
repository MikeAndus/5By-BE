"""phase1 core tables and enums

Revision ID: 20260210_150500
Revises: 
Create Date: 2026-02-10 15:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260210_150500"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.execute("CREATE TYPE topic AS ENUM ('Politics','Science','History','Art','Current Affairs');")
    op.execute("CREATE TYPE session_status AS ENUM ('in_progress','complete');")
    op.execute("CREATE TYPE revealed_by AS ENUM ('question','guess','auto');")
    op.execute(
        "CREATE TYPE event_type AS ENUM ('question_asked','question_answered','letter_guessed','word_guessed');"
    )

    topic_enum = postgresql.ENUM(
        "Politics",
        "Science",
        "History",
        "Art",
        "Current Affairs",
        name="topic",
        create_type=False,
    )
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

    op.create_table(
        "grids",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("cells", sa.CHAR(length=25), nullable=False),
        sa.Column("words_across", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("words_down", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(cells)=25", name="grids_cells_length_check"),
        sa.CheckConstraint("array_length(words_across,1)=5", name="grids_words_across_length_check"),
        sa.CheckConstraint("array_length(words_down,1)=5", name="grids_words_down_length_check"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cells", name="grids_cells_key"),
    )

    op.create_table(
        "sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            session_status_enum,
            server_default=sa.text("'in_progress'::session_status"),
            nullable=False,
        ),
        sa.Column("current_turn", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("player_1_grid_id", sa.BigInteger(), nullable=False),
        sa.Column("player_2_grid_id", sa.BigInteger(), nullable=False),
        sa.Column("player_1_name", sa.String(length=30), nullable=True),
        sa.Column("player_2_name", sa.String(length=30), nullable=True),
        sa.Column("player_1_score", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column("player_2_score", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("current_turn IN (1,2)", name="sessions_current_turn_check"),
        sa.ForeignKeyConstraint(["player_1_grid_id"], ["grids.id"]),
        sa.ForeignKeyConstraint(["player_2_grid_id"], ["grids.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("sessions_status_created_at_idx", "sessions", ["status", "created_at"], unique=False)

    op.create_table(
        "cell_states",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_number", sa.SmallInteger(), nullable=False),
        sa.Column("cell_index", sa.SmallInteger(), nullable=False),
        sa.Column("revealed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("locked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("letter", sa.CHAR(length=1), nullable=True),
        sa.Column("revealed_by", revealed_by_enum, nullable=True),
        sa.Column(
            "topics_used",
            postgresql.ARRAY(topic_enum),
            server_default=sa.text("ARRAY[]::topic[]"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("player_number IN (1,2)", name="cell_states_player_number_check"),
        sa.CheckConstraint("cell_index BETWEEN 0 AND 24", name="cell_states_cell_index_check"),
        sa.CheckConstraint("letter ~ '^[A-Z]$'", name="cell_states_letter_check"),
        sa.CheckConstraint(
            "revealed OR (letter IS NULL AND revealed_by IS NULL)",
            name="cell_states_revealed_consistency_check",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id", "player_number", "cell_index"),
    )
    op.create_index(
        "cell_states_session_player_idx",
        "cell_states",
        ["session_id", "player_number"],
        unique=False,
    )
    op.create_index(
        "cell_states_session_player_locked_idx",
        "cell_states",
        ["session_id", "player_number", "locked"],
        unique=False,
    )

    op.create_table(
        "cell_locks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_number", sa.SmallInteger(), nullable=False),
        sa.Column("cell_index", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("player_number IN (1,2)", name="cell_locks_player_number_check"),
        sa.CheckConstraint("cell_index BETWEEN 0 AND 24", name="cell_locks_cell_index_check"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "cell_locks_session_player_created_idx",
        "cell_locks",
        ["session_id", "player_number", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "cell_locks_session_player_uncleared_idx",
        "cell_locks",
        ["session_id", "player_number"],
        unique=False,
        postgresql_where=sa.text("cleared_at IS NULL"),
    )
    op.create_index(
        "cell_locks_session_player_cell_uncleared_idx",
        "cell_locks",
        ["session_id", "player_number", "cell_index"],
        unique=False,
        postgresql_where=sa.text("cleared_at IS NULL"),
    )

    op.create_table(
        "event_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_number", sa.SmallInteger(), nullable=False),
        sa.Column("type", event_type_enum, nullable=False),
        sa.Column("event_data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("player_number IN (1,2)", name="event_logs_player_number_check"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "event_logs_session_created_idx",
        "event_logs",
        ["session_id", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )
    op.create_index(
        "event_logs_session_player_created_idx",
        "event_logs",
        ["session_id", "player_number", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("event_logs")
    op.drop_table("cell_locks")
    op.drop_table("cell_states")
    op.drop_table("sessions")
    op.drop_table("grids")

    op.execute("DROP TYPE IF EXISTS event_type;")
    op.execute("DROP TYPE IF EXISTS revealed_by;")
    op.execute("DROP TYPE IF EXISTS session_status;")
    op.execute("DROP TYPE IF EXISTS topic;")

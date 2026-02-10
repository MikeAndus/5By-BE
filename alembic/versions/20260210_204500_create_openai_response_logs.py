"""create openai response logs

Revision ID: 20260210_204500
Revises: 20260210_150500
Create Date: 2026-02-10 20:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260210_204500"
down_revision: Union[str, Sequence[str], None] = "20260210_150500"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    topic_enum = postgresql.ENUM(
        "Politics",
        "Science",
        "History",
        "Art",
        "Current Affairs",
        name="topic",
        create_type=False,
    )

    op.create_table(
        "openai_response_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_number", sa.SmallInteger(), nullable=False),
        sa.Column("cell_index", sa.SmallInteger(), nullable=False),
        sa.Column("topic", topic_enum, nullable=False),
        sa.Column("attempt", sa.SmallInteger(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("parsed_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("event_log_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("player_number IN (1, 2)", name="openai_response_logs_player_number_check"),
        sa.CheckConstraint("cell_index BETWEEN 0 AND 24", name="openai_response_logs_cell_index_check"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_log_id"], ["event_logs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "openai_response_logs_session_created_idx",
        "openai_response_logs",
        ["session_id", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )
    op.create_index(
        "openai_response_logs_event_log_id_idx",
        "openai_response_logs",
        ["event_log_id"],
        unique=False,
    )
    op.create_index(
        "openai_response_logs_session_player_cell_idx",
        "openai_response_logs",
        ["session_id", "player_number", "cell_index"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("openai_response_logs_session_player_cell_idx", table_name="openai_response_logs")
    op.drop_index("openai_response_logs_event_log_id_idx", table_name="openai_response_logs")
    op.drop_index("openai_response_logs_session_created_idx", table_name="openai_response_logs")
    op.drop_table("openai_response_logs")

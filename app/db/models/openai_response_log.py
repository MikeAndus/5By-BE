from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import TopicDbEnum


class OpenAiResponseLog(Base):
    __tablename__ = "openai_response_logs"
    __table_args__ = (
        sa.CheckConstraint("player_number IN (1, 2)", name="openai_response_logs_player_number_check"),
        sa.CheckConstraint("cell_index BETWEEN 0 AND 24", name="openai_response_logs_cell_index_check"),
        sa.Index(
            "openai_response_logs_session_created_idx",
            "session_id",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ),
        sa.Index("openai_response_logs_event_log_id_idx", "event_log_id"),
        sa.Index(
            "openai_response_logs_session_player_cell_idx",
            "session_id",
            "player_number",
            "cell_index",
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    player_number: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    cell_index: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    topic: Mapped[TopicDbEnum] = mapped_column(
        sa.Enum(
            TopicDbEnum,
            name="topic",
            native_enum=True,
            create_type=False,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    model: Mapped[str] = mapped_column(sa.Text, nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(postgresql.JSONB, nullable=False)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(postgresql.JSONB, nullable=True)
    parsed_payload: Mapped[dict[str, Any] | None] = mapped_column(postgresql.JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    event_log_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("event_logs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import EventTypeDbEnum


class EventLog(Base):
    __tablename__ = "event_logs"
    __table_args__ = (
        sa.CheckConstraint("player_number IN (1, 2)", name="event_logs_player_number_check"),
        sa.Index(
            "event_logs_session_created_idx",
            "session_id",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ),
        sa.Index(
            "event_logs_session_player_created_idx",
            "session_id",
            "player_number",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    player_number: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    type: Mapped[EventTypeDbEnum] = mapped_column(
        sa.Enum(
            EventTypeDbEnum,
            name="event_type",
            native_enum=True,
            create_type=False,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )
    event_data: Mapped[dict[str, Any]] = mapped_column(
        postgresql.JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

from __future__ import annotations

from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import SessionStatusDbEnum


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        sa.CheckConstraint("current_turn IN (1, 2)", name="sessions_current_turn_check"),
        sa.Index("sessions_status_created_at_idx", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )
    status: Mapped[SessionStatusDbEnum] = mapped_column(
        sa.Enum(
            SessionStatusDbEnum,
            name="session_status",
            native_enum=True,
            create_type=False,
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
        server_default=sa.text("'in_progress'::session_status"),
    )
    current_turn: Mapped[int] = mapped_column(
        sa.SmallInteger,
        nullable=False,
        server_default=sa.text("1"),
    )
    player_1_grid_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("grids.id"),
        nullable=False,
    )
    player_2_grid_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("grids.id"),
        nullable=False,
    )
    player_1_name: Mapped[str | None] = mapped_column(sa.String(30), nullable=True)
    player_2_name: Mapped[str | None] = mapped_column(sa.String(30), nullable=True)
    player_1_score: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("100"))
    player_2_score: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("100"))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        onupdate=sa.func.now(),
    )

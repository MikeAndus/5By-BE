from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import RevealedBy


class CellState(Base):
    __tablename__ = "cell_states"
    __table_args__ = (
        sa.CheckConstraint("player_id IN (1, 2)", name="ck_cell_states_player_id"),
        sa.CheckConstraint("cell_index BETWEEN 0 AND 24", name="ck_cell_states_cell_index"),
        sa.CheckConstraint(
            "array_length(topics_used, 1) IS NULL OR array_length(topics_used, 1) <= 5",
            name="ck_cell_states_topics_used_max_len",
        ),
        sa.Index("cell_states_session_player_idx", "session_id", "player_id"),
        sa.Index("cell_states_session_idx", "session_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    )
    player_id: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True)
    cell_index: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True)
    revealed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    locked: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    topics_used: Mapped[list[str]] = mapped_column(
        ARRAY(sa.TEXT()),
        nullable=False,
        server_default=sa.text("'{}'::text[]"),
    )
    revealed_by: Mapped[RevealedBy | None] = mapped_column(
        sa.Enum(
            RevealedBy,
            name="revealed_by",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            validate_strings=True,
        ),
        nullable=True,
    )
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

    session: Mapped["Session"] = relationship("Session", back_populates="cell_states", lazy="selectin")


__all__ = ["CellState"]

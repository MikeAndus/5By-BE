from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Grid(Base):
    __tablename__ = "grids"
    __table_args__ = (
        sa.CheckConstraint("array_length(cells, 1) = 25", name="ck_grids_cells_len"),
        sa.CheckConstraint("array_length(words_across, 1) = 5", name="ck_grids_words_across_len"),
        sa.CheckConstraint("array_length(words_down, 1) = 5", name="ck_grids_words_down_len"),
    )

    grid_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cells: Mapped[list[str]] = mapped_column(ARRAY(sa.CHAR(length=1)), nullable=False)
    words_across: Mapped[list[str]] = mapped_column(ARRAY(sa.TEXT()), nullable=False)
    words_down: Mapped[list[str]] = mapped_column(ARRAY(sa.TEXT()), nullable=False)
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

    player_1_sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="player_1_grid",
        foreign_keys="Session.player_1_grid_id",
        lazy="selectin",
    )
    player_2_sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="player_2_grid",
        foreign_keys="Session.player_2_grid_id",
        lazy="selectin",
    )


__all__ = ["Grid"]

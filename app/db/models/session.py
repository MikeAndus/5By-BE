from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import SessionStatus


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        sa.CheckConstraint("current_turn IN (1, 2)", name="ck_sessions_current_turn"),
        sa.Index("ix_sessions_status", "status"),
        sa.Index("ix_sessions_updated_at", "updated_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    player_1_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    player_2_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    player_1_name: Mapped[str | None] = mapped_column(sa.String(length=30), nullable=True)
    player_2_name: Mapped[str | None] = mapped_column(sa.String(length=30), nullable=True)
    player_1_grid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("grids.grid_id", ondelete="RESTRICT"),
        nullable=False,
    )
    player_2_grid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("grids.grid_id", ondelete="RESTRICT"),
        nullable=False,
    )
    current_turn: Mapped[int] = mapped_column(
        sa.SmallInteger,
        nullable=False,
        server_default=sa.text("1"),
    )
    player_1_score: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("100"))
    player_2_score: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("100"))
    status: Mapped[SessionStatus] = mapped_column(
        sa.Enum(
            SessionStatus,
            name="session_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
        server_default=sa.text("'in_progress'::session_status"),
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

    player_1_grid: Mapped["Grid"] = relationship(
        "Grid",
        back_populates="player_1_sessions",
        foreign_keys=[player_1_grid_id],
        lazy="selectin",
    )
    player_2_grid: Mapped["Grid"] = relationship(
        "Grid",
        back_populates="player_2_sessions",
        foreign_keys=[player_2_grid_id],
        lazy="selectin",
    )
    cell_states: Mapped[list["CellState"]] = relationship(
        "CellState",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    event_logs: Mapped[list["EventLog"]] = relationship(
        "EventLog",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


__all__ = ["Session"]

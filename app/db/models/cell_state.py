from __future__ import annotations

from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import RevealedByDbEnum, TopicDbEnum


class CellState(Base):
    __tablename__ = "cell_states"
    __table_args__ = (
        sa.CheckConstraint("player_number IN (1, 2)", name="cell_states_player_number_check"),
        sa.CheckConstraint("cell_index BETWEEN 0 AND 24", name="cell_states_cell_index_check"),
        sa.CheckConstraint("letter ~ '^[A-Z]$'", name="cell_states_letter_check"),
        sa.CheckConstraint(
            "revealed OR (letter IS NULL AND revealed_by IS NULL)",
            name="cell_states_revealed_consistency_check",
        ),
        sa.Index("cell_states_session_player_idx", "session_id", "player_number"),
        sa.Index(
            "cell_states_session_player_locked_idx",
            "session_id",
            "player_number",
            "locked",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("sessions.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    player_number: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True, nullable=False)
    cell_index: Mapped[int] = mapped_column(sa.SmallInteger, primary_key=True, nullable=False)
    revealed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    locked: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    letter: Mapped[str | None] = mapped_column(sa.CHAR(1), nullable=True)
    revealed_by: Mapped[RevealedByDbEnum | None] = mapped_column(
        sa.Enum(
            RevealedByDbEnum,
            name="revealed_by",
            native_enum=True,
            create_type=False,
        ),
        nullable=True,
    )
    topics_used: Mapped[list[TopicDbEnum]] = mapped_column(
        postgresql.ARRAY(
            sa.Enum(
                TopicDbEnum,
                name="topic",
                native_enum=True,
                create_type=False,
                values_callable=lambda e: [x.value for x in e],
            )
        ),
        nullable=False,
        server_default=sa.text("ARRAY[]::topic[]"),
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

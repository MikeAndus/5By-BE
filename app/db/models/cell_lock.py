from __future__ import annotations

from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CellLock(Base):
    __tablename__ = "cell_locks"
    __table_args__ = (
        sa.CheckConstraint("player_number IN (1, 2)", name="cell_locks_player_number_check"),
        sa.CheckConstraint("cell_index BETWEEN 0 AND 24", name="cell_locks_cell_index_check"),
        sa.Index(
            "cell_locks_session_player_created_idx",
            "session_id",
            "player_number",
            "created_at",
            "id",
        ),
        sa.Index(
            "cell_locks_session_player_uncleared_idx",
            "session_id",
            "player_number",
            postgresql_where=sa.text("cleared_at IS NULL"),
        ),
        sa.Index(
            "cell_locks_session_player_cell_uncleared_idx",
            "session_id",
            "player_number",
            "cell_index",
            postgresql_where=sa.text("cleared_at IS NULL"),
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
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    cleared_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Grid(Base):
    __tablename__ = "grids"
    __table_args__ = (
        sa.CheckConstraint("char_length(cells) = 25", name="grids_cells_length_check"),
        sa.CheckConstraint("array_length(words_across, 1) = 5", name="grids_words_across_length_check"),
        sa.CheckConstraint("array_length(words_down, 1) = 5", name="grids_words_down_length_check"),
        sa.UniqueConstraint("cells", name="grids_cells_key"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    cells: Mapped[str] = mapped_column(sa.CHAR(25), nullable=False)
    words_across: Mapped[list[str]] = mapped_column(postgresql.ARRAY(sa.Text), nullable=False)
    words_down: Mapped[list[str]] = mapped_column(postgresql.ARRAY(sa.Text), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

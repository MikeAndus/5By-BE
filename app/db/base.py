from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy models."""


# Import model modules after Base declaration so metadata is populated for Alembic.
from app.db import models  # noqa: F401,E402


__all__ = ["Base"]

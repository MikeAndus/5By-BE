"""add lobby to session_status enum

Revision ID: 6e981156a8e0
Revises: 20260210_be1_2
Create Date: 2026-02-10 10:25:36.201799

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e981156a8e0'
down_revision: Union[str, None] = '20260210_be1_2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TYPE session_status ADD VALUE IF NOT EXISTS 'lobby' BEFORE 'in_progress'")

def downgrade():
    pass  # can't remove enum values in postgres

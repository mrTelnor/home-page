"""initial

Revision ID: 001_initial
Revises:
Create Date: 2026-06-08 00:47:58.379903
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

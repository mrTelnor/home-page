"""add glyph_kind and glyph_color to recipes

Revision ID: 005
Revises: 004
Create Date: 2026-04-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("glyph_kind", sa.String(20), nullable=True),
        schema="dinner",
    )
    op.add_column(
        "recipes",
        sa.Column("glyph_color", sa.String(20), nullable=True),
        schema="dinner",
    )


def downgrade() -> None:
    op.drop_column("recipes", "glyph_color", schema="dinner")
    op.drop_column("recipes", "glyph_kind", schema="dinner")

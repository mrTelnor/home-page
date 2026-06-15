"""add image_url to recipes

Revision ID: 009
Revises: 008
Create Date: 2026-06-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("image_url", sa.String(length=500), nullable=True),
        schema="dinner",
    )


def downgrade() -> None:
    op.drop_column("recipes", "image_url", schema="dinner")

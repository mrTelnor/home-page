"""fix daily_menu default status to collecting

Revision ID: 002
Revises: 001
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "daily_menus",
        "status",
        server_default="collecting",
        schema="dinner",
    )


def downgrade() -> None:
    op.alter_column(
        "daily_menus",
        "status",
        server_default="voting",
        schema="dinner",
    )

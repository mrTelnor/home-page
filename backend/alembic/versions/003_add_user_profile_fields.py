"""add user profile fields (first_name, birthday, is_volkov, gender)

Revision ID: 003
Revises: 002
Create Date: 2026-04-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("first_name", sa.String(50), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("birthday", sa.Date(), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("is_volkov", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("gender", sa.String(10), nullable=True),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "gender", schema="auth")
    op.drop_column("users", "is_volkov", schema="auth")
    op.drop_column("users", "birthday", schema="auth")
    op.drop_column("users", "first_name", schema="auth")

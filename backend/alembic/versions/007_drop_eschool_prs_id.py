"""drop eschool_prs_id from users (остаток откатённой eschool-интеграции)

Revision ID: 007
Revises: 006
Create Date: 2026-06-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_users_eschool_prs_id", "users", schema="auth", type_="unique")
    op.drop_column("users", "eschool_prs_id", schema="auth")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("eschool_prs_id", sa.Integer(), nullable=True),
        schema="auth",
    )
    op.create_unique_constraint(
        "uq_users_eschool_prs_id",
        "users",
        ["eschool_prs_id"],
        schema="auth",
    )

"""JWT-отзыв: users.token_version.

JWT несёт claim "ver"; смена пароля инкрементит token_version, обесценивая
все ранее выданные токены (отзыв без таблицы сессий).

Revision ID: 013
Revises: 012
"""
import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "token_version", schema="auth")

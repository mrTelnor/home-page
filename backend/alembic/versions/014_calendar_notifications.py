"""Раздельные уведомления: users.calendar_notifications_enabled.

notifications_enabled остаётся переключателем рассылок об ужине;
новый флаг управляет напоминаниями и дайджестом Google Calendar (админам).

Revision ID: 014
Revises: 013
"""
import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "calendar_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "calendar_notifications_enabled", schema="auth")

"""Уведомления трекера: users.tracker_notifications_enabled.

Флаг управляет уведомлениями трекера Vikunja в Telegram (назначение на задачу,
новый комментарий) — отдельно от ужинов и календаря.

Revision ID: 015
Revises: 014
"""
import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "tracker_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "tracker_notifications_enabled", schema="auth")

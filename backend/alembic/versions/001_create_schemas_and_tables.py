"""create auth and dinner schemas with tables

Revision ID: 001
Revises:
Create Date: 2026-03-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    op.execute("CREATE SCHEMA IF NOT EXISTS dinner")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), unique=True, nullable=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="auth",
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(255), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        schema="auth",
    )

    op.create_table(
        "recipes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("servings", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("auth.users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="dinner",
    )

    op.create_table(
        "ingredients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recipe_id", sa.Uuid(), sa.ForeignKey("dinner.recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("amount", sa.String(50), nullable=False),
        sa.Column("unit", sa.String(30), nullable=True),
        schema="dinner",
    )

    op.create_table(
        "daily_menus",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("date", sa.Date(), unique=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="voting"),
        sa.Column("winner_recipe_id", sa.Uuid(), sa.ForeignKey("dinner.recipes.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="dinner",
    )

    op.create_table(
        "daily_menu_recipes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("menu_id", sa.Uuid(), sa.ForeignKey("dinner.daily_menus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), sa.ForeignKey("dinner.recipes.id"), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("added_by", sa.Uuid(), sa.ForeignKey("auth.users.id"), nullable=True),
        schema="dinner",
    )

    op.create_table(
        "votes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("auth.users.id"), nullable=False),
        sa.Column("menu_id", sa.Uuid(), sa.ForeignKey("dinner.daily_menus.id"), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), sa.ForeignKey("dinner.recipes.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "menu_id", name="uq_vote_user_menu"),
        schema="dinner",
    )


def downgrade() -> None:
    op.drop_table("votes", schema="dinner")
    op.drop_table("daily_menu_recipes", schema="dinner")
    op.drop_table("daily_menus", schema="dinner")
    op.drop_table("ingredients", schema="dinner")
    op.drop_table("recipes", schema="dinner")
    op.drop_table("sessions", schema="auth")
    op.drop_table("users", schema="auth")
    op.execute("DROP SCHEMA IF EXISTS dinner")
    op.execute("DROP SCHEMA IF EXISTS auth")

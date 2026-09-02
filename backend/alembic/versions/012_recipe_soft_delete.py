"""Soft-delete рецептов: recipes.deleted_at.

Рецепт, задействованный в истории меню, помечается deleted_at вместо
физического удаления — прячется из книги, но сохраняет название для истории.

Revision ID: 012
Revises: 011
"""
import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema="dinner",
    )
    op.create_index(
        "ix_dinner_recipes_deleted_at", "recipes", ["deleted_at"], schema="dinner"
    )


def downgrade() -> None:
    op.drop_index("ix_dinner_recipes_deleted_at", "recipes", schema="dinner")
    op.drop_column("recipes", "deleted_at", schema="dinner")

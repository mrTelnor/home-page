"""Индексы по FK, UNIQUE(menu_id, recipe_id) и каскад votes.menu_id.

Postgres не создаёт индексы по FK автоматически: выборки голосов/ингредиентов
и проверки FK при удалениях шли seq scan'ом. UNIQUE(menu_id, recipe_id)
закрывает гонку двух параллельных suggest. CASCADE на votes.menu_id чинит
500 при удалении меню с голосами.

Revision ID: 011
Revises: 010
"""
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- индексы по FK / сортировке (имена — как генерирует SQLAlchemy из моделей) ---
    op.create_index("ix_dinner_votes_menu_id", "votes", ["menu_id"], schema="dinner")
    op.create_index("ix_dinner_votes_recipe_id", "votes", ["recipe_id"], schema="dinner")
    op.create_index(
        "ix_dinner_daily_menu_recipes_recipe_id", "daily_menu_recipes", ["recipe_id"], schema="dinner"
    )
    op.create_index("ix_dinner_ingredients_recipe_id", "ingredients", ["recipe_id"], schema="dinner")
    op.create_index("ix_dinner_recipes_author_id", "recipes", ["author_id"], schema="dinner")
    op.create_index("ix_recipes_created_at", "recipes", ["created_at"], schema="dinner")
    op.create_index(
        "ix_dinner_daily_menus_winner_recipe_id", "daily_menus", ["winner_recipe_id"], schema="dinner"
    )

    # --- UNIQUE(menu_id, recipe_id): сначала убираем возможные дубли от прошлых гонок ---
    op.execute(
        """
        DELETE FROM dinner.daily_menu_recipes a
        USING dinner.daily_menu_recipes b
        WHERE a.menu_id = b.menu_id
          AND a.recipe_id = b.recipe_id
          AND a.id > b.id
        """
    )
    op.create_unique_constraint(
        "uq_menu_recipe", "daily_menu_recipes", ["menu_id", "recipe_id"], schema="dinner"
    )

    # --- votes.menu_id: ON DELETE CASCADE ---
    op.drop_constraint("votes_menu_id_fkey", "votes", schema="dinner", type_="foreignkey")
    op.create_foreign_key(
        "votes_menu_id_fkey",
        "votes",
        "daily_menus",
        ["menu_id"],
        ["id"],
        source_schema="dinner",
        referent_schema="dinner",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("votes_menu_id_fkey", "votes", schema="dinner", type_="foreignkey")
    op.create_foreign_key(
        "votes_menu_id_fkey",
        "votes",
        "daily_menus",
        ["menu_id"],
        ["id"],
        source_schema="dinner",
        referent_schema="dinner",
    )
    op.drop_constraint("uq_menu_recipe", "daily_menu_recipes", schema="dinner", type_="unique")
    op.drop_index("ix_dinner_daily_menus_winner_recipe_id", "daily_menus", schema="dinner")
    op.drop_index("ix_recipes_created_at", "recipes", schema="dinner")
    op.drop_index("ix_dinner_recipes_author_id", "recipes", schema="dinner")
    op.drop_index("ix_dinner_ingredients_recipe_id", "ingredients", schema="dinner")
    op.drop_index("ix_dinner_daily_menu_recipes_recipe_id", "daily_menu_recipes", schema="dinner")
    op.drop_index("ix_dinner_votes_recipe_id", "votes", schema="dinner")
    op.drop_index("ix_dinner_votes_menu_id", "votes", schema="dinner")

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

RECIPE_FK = "dinner.recipes.id"
MENU_FK = "dinner.daily_menus.id"
USER_FK = "auth.users.id"


class DailyMenu(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "daily_menus"
    __table_args__ = {"schema": "dinner"}

    date: Mapped[date] = mapped_column(Date, unique=True)
    status: Mapped[str] = mapped_column(String(20), default="collecting")
    winner_recipe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(RECIPE_FK), index=True)

    menu_recipes: Mapped[list["DailyMenuRecipe"]] = relationship(back_populates="menu", cascade="all, delete-orphan")


class DailyMenuRecipe(Base, UUIDMixin):
    __tablename__ = "daily_menu_recipes"
    # UNIQUE(menu_id, recipe_id): дубль предложения, проскочивший гонкой мимо
    # проверки роутера, упирается в БД. Составной индекс заодно покрывает
    # выборки по menu_id (selectinload, count_user_suggestions).
    __table_args__ = (
        UniqueConstraint("menu_id", "recipe_id", name="uq_menu_recipe"),
        {"schema": "dinner"},
    )

    menu_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(MENU_FK, ondelete="CASCADE"))
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(RECIPE_FK), index=True)
    source: Mapped[str] = mapped_column(String(10))
    added_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(USER_FK))

    menu: Mapped["DailyMenu"] = relationship(back_populates="menu_recipes")


class Vote(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("user_id", "menu_id", name="uq_vote_user_menu"),
        {"schema": "dinner"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(USER_FK))
    # CASCADE: удаление меню админом должно уносить голоса, а не падать 500.
    # index=True: uq(user_id, menu_id) не помогает выборкам по menu_id (ведущая колонка не та).
    menu_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(MENU_FK, ondelete="CASCADE"), index=True)
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(RECIPE_FK), index=True)

import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class DailyMenu(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "daily_menus"
    __table_args__ = {"schema": "dinner"}

    date: Mapped[date] = mapped_column(Date, unique=True)
    status: Mapped[str] = mapped_column(String(20), default="voting")
    winner_recipe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("dinner.recipes.id"))

    menu_recipes: Mapped[list["DailyMenuRecipe"]] = relationship(back_populates="menu", cascade="all, delete-orphan")


class DailyMenuRecipe(Base, UUIDMixin):
    __tablename__ = "daily_menu_recipes"
    __table_args__ = {"schema": "dinner"}

    menu_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dinner.daily_menus.id", ondelete="CASCADE"))
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dinner.recipes.id"))
    source: Mapped[str] = mapped_column(String(10))
    added_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("auth.users.id"))

    menu: Mapped["DailyMenu"] = relationship(back_populates="menu_recipes")


class Vote(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("user_id", "menu_id", name="uq_vote_user_menu"),
        {"schema": "dinner"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id"))
    menu_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dinner.daily_menus.id"))
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dinner.recipes.id"))

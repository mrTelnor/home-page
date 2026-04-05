import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Recipe(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "recipes"
    __table_args__ = {"schema": "dinner"}

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    servings: Mapped[int] = mapped_column(Integer, default=4)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    ingredients: Mapped[list["Ingredient"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")


class Ingredient(Base, UUIDMixin):
    __tablename__ = "ingredients"
    __table_args__ = {"schema": "dinner"}

    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dinner.recipes.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    amount: Mapped[str] = mapped_column(String(50))
    unit: Mapped[str | None] = mapped_column(String(30))

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")

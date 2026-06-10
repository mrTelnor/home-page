import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    tg_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    first_name: Mapped[str | None] = mapped_column(String(50))
    birthday: Mapped[date | None] = mapped_column(Date)
    is_volkov: Mapped[bool] = mapped_column(Boolean, default=False)
    gender: Mapped[str | None] = mapped_column(String(10))
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base, UUIDMixin):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "auth"}

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime]

    user: Mapped["User"] = relationship(back_populates="sessions")

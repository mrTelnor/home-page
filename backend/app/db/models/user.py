from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

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
    # Рассылки об ужине (меню, голосование, результаты)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Напоминания и утренний дайджест Google Calendar (получают только админы)
    calendar_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Версия токенов: JWT несёт её в claim "ver"; смена пароля инкрементит,
    # обесценивая все ранее выданные токены (отзыв без таблицы сессий).
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

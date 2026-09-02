import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin


class PasswordResetToken(Base, UUIDMixin):
    __tablename__ = "password_reset_tokens"
    # Явное имя индекса под уже созданный миграцией 010 (без схемного префикса,
    # который дал бы index=True) — иначе autogenerate предлагает его пересоздать.
    __table_args__ = (
        Index("ix_password_reset_tokens_user_id", "user_id"),
        {"schema": "auth"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

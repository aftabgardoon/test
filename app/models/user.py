"""``users`` table: one row per registered user."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """A person using the sync bot.

    A user is identified by the platform they signed up on and their platform
    user id (unique together).
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("platform", "platform_user_id", name="uq_users_platform_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    platform_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    channels: Mapped[list["Channel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sync_links: Mapped[list["SyncLink"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

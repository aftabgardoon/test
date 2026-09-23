"""``authorized_users`` table: users allowed to use the manager bot.

The manager UI is private: nobody sees any content (menu, channels, links)
until they send the secret command ``/RSAsecret``.  Every granted user is
recorded here so the unlock survives restarts.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuthorizedUser(Base):
    """A person who has unlocked the manager bot with the secret command."""

    __tablename__ = "authorized_users"
    __table_args__ = (
        UniqueConstraint(
            "platform", "platform_user_id", name="uq_authorized_platform_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    platform_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

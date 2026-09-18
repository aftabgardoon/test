"""``bot_tokens`` table: encrypted bot tokens per platform and owner."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BotToken(Base):
    """An encrypted bot token used to talk to a given platform.

    ``token`` is stored encrypted (Fernet). ``owner_user_id`` may be ``NULL``
    for a platform-wide default token.
    """

    __tablename__ = "bot_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

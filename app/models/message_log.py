"""``message_logs`` table: audit trail of every synchronised message."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MessageStatus(StrEnum):
    """Lifecycle state of a synchronised message."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class MessageLog(Base):
    """A record mapping a source message to its destination copy."""

    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sync_link_id: Mapped[int] = mapped_column(
        ForeignKey("sync_links.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=MessageStatus.PENDING, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sync_link: Mapped["SyncLink"] = relationship()  # noqa: F821,UP037

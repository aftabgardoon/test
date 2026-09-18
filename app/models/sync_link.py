"""``sync_links`` table: a source channel linked to a destination channel."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base

# ``JSON`` works for PostgreSQL; aiosqlite benefits from the SQLite variant.
JSONType = JSON().with_variant(SQLiteJSON(), "sqlite")


class SyncLink(Base):
    """A synchronisation rule between one source and one destination channel.

    ``filters`` is a JSON object, e.g.::

        {
            "message_types": ["text", "photo"],
            "keywords": ["sale"],
            "remove_signature": false,
            "strip_forward": true
        }
    """

    __tablename__ = "sync_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination_channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filters: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="sync_links")
    source_channel: Mapped["Channel"] = relationship(foreign_keys=[source_channel_id])
    destination_channel: Mapped["Channel"] = relationship(
        foreign_keys=[destination_channel_id]
    )

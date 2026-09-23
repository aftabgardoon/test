"""Pydantic schemas for sync links."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SyncLinkCreate(BaseModel):
    """Payload used to create a synchronisation link."""

    source_channel_id: int
    destination_channel_id: int
    filters: dict[str, Any] | None = None
    is_active: bool = True


class SyncLinkRead(BaseModel):
    """Serialised representation of a sync link."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    source_channel_id: int
    destination_channel_id: int
    filters: dict[str, Any] | None
    is_active: bool
    created_at: datetime

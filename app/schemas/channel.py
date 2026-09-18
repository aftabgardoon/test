"""Pydantic schemas for channels."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChannelCreate(BaseModel):
    """Payload used to register a channel."""

    platform: str
    platform_channel_id: str = Field(min_length=1, max_length=128)
    title: str | None = None
    role: str = "source"
    is_active: bool = True


class ChannelRead(BaseModel):
    """Serialised representation of a channel."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    platform: str
    platform_channel_id: str
    title: str | None
    role: str
    is_active: bool
    created_at: datetime

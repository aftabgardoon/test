"""Pydantic schemas for users."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    """Payload used to register a user."""

    platform: str
    platform_user_id: str
    username: str | None = None


class UserRead(BaseModel):
    """Serialised representation of a user."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    platform_user_id: str
    username: str | None
    created_at: datetime

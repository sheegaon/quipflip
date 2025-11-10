"""Schemas for online users endpoints."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List


class OnlineUser(BaseModel):
    """Schema for an online user."""

    model_config = ConfigDict(from_attributes=True)

    username: str
    last_action: str
    last_activity: datetime
    time_ago: str


class OnlineUsersResponse(BaseModel):
    """Response schema for online users list."""

    users: List[OnlineUser]
    total_count: int

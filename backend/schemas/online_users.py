"""Pydantic schemas for "Who's Online" feature endpoints.

Defines request/response schemas for REST and WebSocket endpoints that show
which users are currently active based on recent API calls.

This is distinct from phraseset_activity schemas, which handle historical
phraseset review events.
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List


class OnlineUser(BaseModel):
    """Schema for a single online user in the "Who's Online" page."""

    model_config = ConfigDict(from_attributes=True)

    username: str
    last_action: str
    last_activity: datetime
    time_ago: str


class OnlineUsersResponse(BaseModel):
    """Response schema for online users list in the "Who's Online" feature."""

    users: List[OnlineUser]
    total_count: int

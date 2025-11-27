"""Pydantic schemas for "Who's Online" feature endpoints.

Defines request/response schemas for REST and WebSocket endpoints that show
which users are currently active based on recent API calls.

This is distinct from phraseset_activity schemas, which handle historical
phraseset review events.
"""
from datetime import datetime
from typing import List

from backend.schemas.base import BaseSchema


class OnlineUser(BaseSchema):
    """Schema for a single online user in the "Who's Online" page."""

    username: str
    last_action: str
    last_action_category: str
    last_activity: datetime
    time_ago: str
    wallet: int
    created_at: datetime


class OnlineUsersResponse(BaseSchema):
    """Response schema for online users list in the "Who's Online" feature."""

    users: List[OnlineUser]
    total_count: int


class PingUserRequest(BaseSchema):
    """Payload for pinging a specific online user."""

    username: str


class PingUserResponse(BaseSchema):
    """Response after issuing a ping to another user."""

    success: bool
    message: str

"""Schemas for notification WebSocket messages and API responses."""

from typing import Optional

from pydantic import BaseModel


class NotificationWebSocketMessage(BaseModel):
    """Message sent via WebSocket to clients."""

    type: str = "notification"
    notification_type: str  # 'copy_submitted' or 'vote_submitted'
    actor_username: str
    action: str  # 'copied' or 'voted on'
    recipient_role: str  # 'prompt' or 'copy'
    phrase_text: str  # Truncated to 50 chars with "..." if longer
    timestamp: str  # ISO format datetime


class PingWebSocketMessage(BaseModel):
    """Lightweight ping message delivered over the notification WebSocket."""

    type: str = "ping"
    from_username: str
    timestamp: str  # ISO format datetime
    join_url: str | None = None


class NotificationCreate(BaseModel):
    """Internal schema for creating notifications."""

    notification_type: str
    phraseset_id: str
    actor_player_id: Optional[str] = None
    metadata: Optional[dict] = None

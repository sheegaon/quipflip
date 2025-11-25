"""Base Notification model with common fields and functionality."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


def get_current_utc():
    """Get current UTC datetime."""
    from datetime import timezone
    return datetime.now(timezone.utc)


class NotificationBase(Base):
    """Base notification model for WebSocket push notifications."""
    
    __abstract__ = True

    notification_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(nullable=False, index=True)
    notification_type = Column(String(50), nullable=False)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_current_utc, nullable=False)

    def __repr__(self) -> str:
        return (f"<{self.__class__.__name__}"
                f"(id={self.notification_id}, type={self.notification_type}, player={self.player_id})>")

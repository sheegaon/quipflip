"""
Notification model for WebSocket push notifications.

Stores notifications sent to players when other human players interact with
their phrasesets (copy submissions and votes).
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


def get_current_utc():
    """Get current UTC datetime."""
    from datetime import timezone
    return datetime.now(timezone.utc)


class Notification(Base):
    """
    Notification record for WebSocket push notifications.

    Tracks notifications sent to players when:
    - Another human copies their prompt
    - Another human votes on a phraseset they contributed to
    """

    __tablename__ = "notifications"

    notification_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_type = Column(
        String(50), nullable=False
    )  # 'copy_submitted' or 'vote_submitted'
    phraseset_id = get_uuid_column(
        ForeignKey("phrasesets.phraseset_id", ondelete="CASCADE"), nullable=False
    )
    actor_player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), nullable=True
    )
    data = Column(JSON, nullable=True)  # {phrase_text, recipient_role, actor_username}
    created_at = Column(DateTime(timezone=True), default=get_current_utc, nullable=False)

    # Relationships
    player = relationship("Player", foreign_keys=[player_id])
    actor_player = relationship("Player", foreign_keys=[actor_player_id])
    phraseset = relationship("Phraseset")

    # Indexes for efficient querying
    __table_args__ = (
        Index("ix_notifications_player_created", "player_id", "created_at"),
        Index("ix_notifications_phraseset", "phraseset_id"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.notification_id}, type={self.notification_type}, player={self.player_id})>"

"""
Notification model for WebSocket push notifications.

Stores notifications sent to players when other human players interact with
their phrasesets (copy submissions and votes).
"""
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.models.notification_base import NotificationBase
from backend.models.base import get_uuid_column


class QFNotification(NotificationBase):
    """
    Notification record for WebSocket push notifications.

    Tracks notifications sent to players when:
    - Another human copies their prompt
    - Another human votes on a phraseset they contributed to
    """

    __tablename__ = "qf_notifications"

    # Override player_id to add QF-specific foreign key constraint
    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # QF-specific fields
    phraseset_id = get_uuid_column(
        ForeignKey("qf_phrasesets.phraseset_id", ondelete="CASCADE"), nullable=False
    )
    actor_player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), nullable=True
    )

    # Relationships
    player = relationship("Player", foreign_keys=[player_id])
    actor_player = relationship("Player", foreign_keys=[actor_player_id])
    phraseset = relationship("Phraseset")

    # Indexes for efficient querying
    __table_args__ = (
        Index("ix_notifications_player_created", "player_id", "created_at"),
        Index("ix_notifications_phraseset", "phraseset_id"),
    )

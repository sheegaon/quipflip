"""
Notification model for WebSocket push notifications.

Stores notifications sent to players when other human players interact with
their backronym entries (submissions and votes).
"""
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.models.notification_base import NotificationBase
from backend.models.base import get_uuid_column


class IRNotification(NotificationBase):
    """
    Notification record for WebSocket push notifications.

    Tracks notifications sent to players when:
    - Another human votes on their backronym entry
    - Another human submits to a set they contributed to
    """

    __tablename__ = "ir_notifications"

    # Override player_id to add IR-specific foreign key constraint
    player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # IR-specific fields
    backronym_set_id = get_uuid_column(
        ForeignKey("ir_backronym_sets.set_id", ondelete="CASCADE"), nullable=False
    )
    actor_player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"), nullable=True
    )

    # Relationships
    player = relationship("IRPlayer", foreign_keys=[player_id])
    actor_player = relationship("IRPlayer", foreign_keys=[actor_player_id])
    backronym_set = relationship("BackronymSet")

    # Indexes for efficient querying
    __table_args__ = (
        Index("ix_notifications_player_created", "player_id", "created_at"),
        Index("ix_notifications_backronym_set", "backronym_set_id"),
    )
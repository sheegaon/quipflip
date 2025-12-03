"""Phraseset activity model for tracking lifecycle events.

Logs historical events in the phraseset review process (creation, review, approval,
rejection, etc.) for analytics and audit purposes.

This is distinct from UserActivity model, which tracks real-time online user status
for the "Who's Online" feature.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid

from backend.database import Base
from backend.models.player import Player
from backend.models.base import get_uuid_column


class PhrasesetActivity(Base):
    """Activity log entry for a phraseset's lifecycle events.

    Tracks historical events like creation, review, approval, rejection, etc.
    Used for displaying phraseset history timelines and analytics.
    """
    __tablename__ = "qf_phraseset_activity"

    activity_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    phraseset_id = get_uuid_column(ForeignKey("qf_phrasesets.phraseset_id"), nullable=True, index=True)
    prompt_round_id = get_uuid_column(ForeignKey("qf_rounds.round_id"), nullable=True, index=True)
    activity_type = Column(String(50), nullable=False)
    player_id = get_uuid_column(ForeignKey("players.player_id", ondelete="CASCADE"), nullable=True, index=True)
    payload = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    phraseset = relationship("Phraseset", back_populates="activities")
    prompt_round = relationship("Round", foreign_keys=[prompt_round_id])
    player = relationship(Player, back_populates="phraseset_activities")

    __table_args__ = (
        Index("ix_phraseset_activity_phraseset_id_created", "phraseset_id", "created_at"),
        Index("ix_phraseset_activity_prompt_round_id_created", "prompt_round_id", "created_at"),
        Index("ix_phraseset_activity_player_id_created", "player_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<PhrasesetActivity(activity_id={self.activity_id}, "
            f"type={self.activity_type}, phraseset_id={self.phraseset_id})>"
        )

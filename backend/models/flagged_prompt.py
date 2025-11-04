"""Model for tracking flagged prompt phrases."""
from __future__ import annotations

from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid

from backend.database import Base
from backend.models.base import get_uuid_column


class FlaggedPrompt(Base):
    """Stores copy round flags for prompt phrases pending admin review."""

    __tablename__ = "flagged_prompts"

    flag_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    prompt_round_id = get_uuid_column(
        ForeignKey("rounds.round_id", ondelete="CASCADE"), nullable=False, index=True
    )
    copy_round_id = get_uuid_column(
        ForeignKey("rounds.round_id", ondelete="SET NULL"), nullable=True, index=True
    )
    reporter_player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String(20), default="pending", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="SET NULL"), nullable=True, index=True
    )
    original_phrase = Column(String(100), nullable=False)
    prompt_text = Column(String(500), nullable=True)
    previous_phraseset_status = Column(String(20), nullable=True)
    queue_removed = Column(Boolean, default=False, nullable=False)
    round_cost = Column(Integer, nullable=False)
    partial_refund_amount = Column(Integer, nullable=False)
    penalty_kept = Column(Integer, nullable=False)

    # Relationships
    reporter = relationship("Player", foreign_keys=[reporter_player_id])
    prompt_player = relationship("Player", foreign_keys=[prompt_player_id])
    reviewer = relationship("Player", foreign_keys=[reviewer_player_id])
    prompt_round = relationship("Round", foreign_keys=[prompt_round_id])
    copy_round = relationship("Round", foreign_keys=[copy_round_id])

    def __repr__(self) -> str:
        return f"<FlaggedPrompt(flag_id={self.flag_id}, prompt_round_id={self.prompt_round_id}, status={self.status})>"

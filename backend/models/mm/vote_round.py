"""Meme Mint vote round model capturing entry, payouts, and choices."""
import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, Integer, DateTime, ForeignKey, Index, Boolean, JSON
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class MMVoteRound(Base):
    """Represents a single voting round for a player."""

    __tablename__ = "mm_vote_rounds"

    round_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False
    )
    image_id = get_uuid_column(
        ForeignKey("mm_images.image_id", ondelete="CASCADE"), nullable=False
    )
    caption_ids_shown = Column(JSON, nullable=False)
    chosen_caption_id = get_uuid_column(
        ForeignKey("mm_captions.caption_id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    entry_cost = Column(Integer, nullable=False)
    payout_to_wallet = Column(Integer, default=0, nullable=False)
    payout_to_vault = Column(Integer, default=0, nullable=False)

    first_vote_bonus_applied = Column(Boolean, default=False, nullable=False)
    result_finalized_at = Column(DateTime(timezone=True), nullable=True)
    abandoned = Column(Boolean, default=False, nullable=False)

    # Relationships
    player = relationship("MMPlayer", back_populates="vote_rounds")
    image = relationship("MMImage", back_populates="vote_rounds")
    chosen_caption = relationship("MMCaption", back_populates="vote_rounds", foreign_keys=[chosen_caption_id])

    __table_args__ = (
        Index("ix_mm_vote_round_player_created", "player_id", "created_at"),
        Index("ix_mm_vote_round_image_created", "image_id", "created_at"),
        Index("ix_mm_vote_round_chosen_caption", "chosen_caption_id"),
    )

    def __repr__(self) -> str:
        return f"<MMVoteRound(round_id={self.round_id}, abandoned={self.abandoned})>"

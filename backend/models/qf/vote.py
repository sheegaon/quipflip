"""Vote model."""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class Vote(Base):
    """Vote model."""
    __tablename__ = "qf_votes"

    vote_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    phraseset_id = get_uuid_column(ForeignKey("qf_phrasesets.phraseset_id"), nullable=False, index=True)
    player_id = get_uuid_column(ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    voted_phrase = Column(String(100), nullable=False)
    correct = Column(Boolean, nullable=False)
    payout = Column(Integer, nullable=False)  # 5 or 0
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    # Relationships
    phraseset = relationship("Phraseset", back_populates="votes")
    player = relationship("Player", back_populates="votes")

    # Constraints
    __table_args__ = (
        UniqueConstraint('player_id', 'phraseset_id', name='uq_player_phraseset_vote'),
        Index('ix_votes_phraseset_player', 'phraseset_id', 'player_id'),
    )

    def __repr__(self):
        return f"<Vote(vote_id={self.vote_id}, correct={self.correct}, payout={self.payout})>"

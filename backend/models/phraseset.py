"""Phraseset model."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class Phraseset(Base):
    """Phraseset model for voting."""
    __tablename__ = "phrasesets"

    phraseset_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    prompt_round_id = get_uuid_column(ForeignKey("rounds.round_id"), nullable=False, index=True)
    copy_round_1_id = get_uuid_column(ForeignKey("rounds.round_id"), nullable=False)
    copy_round_2_id = get_uuid_column(ForeignKey("rounds.round_id"), nullable=False)

    # Denormalized fields for performance
    prompt_text = Column(String(500), nullable=False)
    original_phrase = Column(String(100), nullable=False)  # Prompt player's phrase
    copy_phrase_1 = Column(String(100), nullable=False)
    copy_phrase_2 = Column(String(100), nullable=False)

    # Vote lifecycle
    status = Column(String(20), nullable=False, default="open")  # open, closing, closed, finalized
    vote_count = Column(Integer, default=0, nullable=False)
    third_vote_at = Column(DateTime(timezone=True), nullable=True)
    fifth_vote_at = Column(DateTime(timezone=True), nullable=True, index=True)
    closes_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    finalized_at = Column(DateTime(timezone=True), nullable=True)

    # Prize pool tracking
    total_pool = Column(Integer, default=200, nullable=False)  # Dynamic: base + vote contributions - correct payouts
    vote_contributions = Column(Integer, default=0, nullable=False)  # Total vote_cost added from votes
    vote_payouts_paid = Column(Integer, default=0, nullable=False)  # Total vote_payout_correct paid out
    system_contribution = Column(Integer, default=0, nullable=False)  # Copy discount contributions (0, 10, or 20)

    # Relationships
    prompt_round = relationship("Round", foreign_keys=[prompt_round_id])
    copy_round_1 = relationship("Round", foreign_keys=[copy_round_1_id])
    copy_round_2 = relationship("Round", foreign_keys=[copy_round_2_id])
    votes = relationship("Vote", back_populates="phraseset")
    vote_rounds = relationship("Round", back_populates="phraseset", foreign_keys="Round.phraseset_id")
    result_views = relationship("ResultView", back_populates="phraseset")
    activities = relationship(
        "PhrasesetActivity",
        back_populates="phraseset",
        order_by="PhrasesetActivity.created_at",
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index('ix_phrasesets_status_vote_count', 'status', 'vote_count'),
        Index('ix_phrasesets_status_fifth_vote_at', 'status', 'fifth_vote_at'),
        Index('ix_phrasesets_status_third_vote_at', 'status', 'third_vote_at'),
        Index('ix_phrasesets_status_created_at', 'status', 'created_at'),
    )

    def __repr__(self):
        return f"<Phraseset(phraseset_id={self.phraseset_id}, status={self.status}, vote_count={self.vote_count})>"

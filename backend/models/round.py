"""Unified round model for prompt, copy, and vote rounds."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class Round(Base):
    """Unified round model for all round types."""
    __tablename__ = "rounds"

    round_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    round_type = Column(String(20), nullable=False)  # prompt, copy, vote
    status = Column(String(20), nullable=False)  # active, submitted, expired, abandoned
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    cost = Column(Integer, nullable=False)  # 100, 90, or 1

    # Prompt-specific fields (nullable for non-prompt rounds)
    prompt_id = get_uuid_column(ForeignKey("prompts.prompt_id"), nullable=True)
    prompt_text = Column(String(500), nullable=True)  # Denormalized
    submitted_phrase = Column(String(100), nullable=True)  # Prompt player's phrase
    phraseset_status = Column(String(20), nullable=True)  # waiting_copies, waiting_copy1, active, finalized, abandoned
    copy1_player_id = get_uuid_column(ForeignKey("players.player_id", ondelete="CASCADE"), nullable=True, index=True)
    copy2_player_id = get_uuid_column(ForeignKey("players.player_id", ondelete="CASCADE"), nullable=True, index=True)

    # Copy-specific fields (nullable for non-copy rounds)
    prompt_round_id = get_uuid_column(ForeignKey("rounds.round_id"), nullable=True, index=True)
    original_phrase = Column(String(100), nullable=True)  # Phrase to copy
    copy_phrase = Column(String(100), nullable=True)  # Copy player's submitted phrase
    system_contribution = Column(Integer, default=0, nullable=False)  # 0 or 10

    # Vote-specific fields (nullable for non-vote rounds)
    phraseset_id = get_uuid_column(ForeignKey("phrasesets.phraseset_id"), nullable=True, index=True)
    vote_submitted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    player = relationship("Player", back_populates="rounds", foreign_keys=[player_id])
    prompt = relationship("Prompt", back_populates="rounds")
    phraseset = relationship("PhraseSet", back_populates="vote_rounds", foreign_keys=[phraseset_id])
    copy1_player = relationship("Player", foreign_keys=[copy1_player_id])
    copy2_player = relationship("Player", foreign_keys=[copy2_player_id])

    # Self-referential for copy rounds
    prompt_round = relationship("Round", remote_side=[round_id], foreign_keys=[prompt_round_id])

    # Indexes
    __table_args__ = (
        Index('ix_rounds_status_created', 'status', 'created_at'),
        Index('ix_rounds_phraseset_status', 'phraseset_status'),
    )

    def __repr__(self):
        return f"<Round(round_id={self.round_id}, type={self.round_type}, status={self.status})>"

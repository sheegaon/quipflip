"""AI phrase cache model for storing pre-validated copy phrases."""

from sqlalchemy import Column, String, DateTime, Boolean, JSON, Index, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class AIPhraseCache(Base):
    """
    AI phrase cache for storing validated copy phrases generated per prompt round.

    Eliminates redundant AI API calls by storing multiple validated phrases that can be
    reused for AI backup copies and hints. Each prompt round gets one cache entry with
    3-5 validated phrases that meet all copy validation requirements.

    Design:
    - Generate once, use multiple times (backup copies + hints)
    - Backup copies consume phrases (removed from list after use)
    - Hints don't consume phrases (all players get same hints)
    - Random selection prevents bias toward first generated phrase
    - Unique constraint on prompt_round_id prevents duplicate generation
    """
    __tablename__ = "ai_phrase_cache"

    cache_id = get_uuid_column(primary_key=True, default=uuid.uuid4)

    # Foreign key to the prompt round this cache is for
    prompt_round_id = get_uuid_column(
        ForeignKey("rounds.round_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Denormalized data from prompt round for context
    original_phrase = Column(String(100), nullable=False)
    prompt_text = Column(String(500), nullable=True)

    # The validated phrases (3-5 strings)
    validated_phrases = Column(JSON, nullable=False)

    # AI provider metadata
    generation_provider = Column(String(50), nullable=False)  # "openai" or "gemini"
    generation_model = Column(String(100), nullable=False)  # e.g., "gpt-5-nano"

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Usage tracking
    used_for_backup_copy = Column(Boolean, default=False, nullable=False)
    used_for_hints = Column(Boolean, default=False, nullable=False)

    # Relationships
    prompt_round = relationship("Round", foreign_keys=[prompt_round_id], backref="ai_phrase_cache")

    # Indexes for common queries
    __table_args__ = (
        Index('ix_ai_phrase_cache_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<AIPhraseCache(prompt_round_id={self.prompt_round_id}, phrases={len(self.validated_phrases)})>"

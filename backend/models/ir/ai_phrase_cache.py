"""IR AIPhraseCache model."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class AIPhraseCache(Base):
    """Cache for AI-generated backronym words."""

    __tablename__ = "ir_ai_phrase_cache"

    cache_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    prompt_round_id = get_uuid_column(
        ForeignKey("ir_backronym_sets.set_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    original_phrase = Column(String(5), nullable=True)  # The word being used (nullable for backward compatibility)
    prompt_text = Column(String(500), nullable=True)  # Optional context
    validated_phrases = Column(JSON, nullable=False)  # Array of 3-5 validated backronym words
    generation_provider = Column(String(50), nullable=False)  # openai, gemini
    generation_model = Column(String(100), nullable=False)
    used_for_backup_copy = Column(Boolean, default=False, nullable=False)
    used_for_hints = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Relationships
    metrics = relationship(
        "IRAIMetric", back_populates="phrase_cache", cascade="all, delete-orphan"
    )

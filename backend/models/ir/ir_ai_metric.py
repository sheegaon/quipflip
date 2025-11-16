"""IR AIMetric model."""
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Boolean,
    Float,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class IRAIMetric(Base):
    """AI generation metrics for Initial Reaction."""

    __tablename__ = "ir_ai_metrics"

    metric_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    operation_type = Column(
        String(50), nullable=False, index=True
    )  # backronym_generation, vote_generation
    provider = Column(String(50), nullable=False, index=True)  # openai, gemini
    model = Column(String(100), nullable=False)
    success = Column(Boolean, nullable=False, index=True)
    latency_ms = Column(Integer, nullable=True)
    error_message = Column(String(500), nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)
    prompt_length = Column(Integer, nullable=True)
    response_length = Column(Integer, nullable=True)
    validation_passed = Column(Boolean, nullable=True)  # For backronym generation
    vote_correct = Column(Boolean, nullable=True)  # For vote generation
    cache_id = get_uuid_column(
        ForeignKey("ir_ai_phrase_cache.cache_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Relationships
    phrase_cache = relationship("IRAIPhraseCache", back_populates="metrics")

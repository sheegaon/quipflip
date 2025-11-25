"""IR AIMetric model."""
from sqlalchemy import Column, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.ai_metric_base import AIMetricBase
from backend.models.base import get_uuid_column


class IRAIMetric(AIMetricBase):
    """AI generation metrics for Initial Reaction."""

    __tablename__ = "ir_ai_metrics"

    # IR-specific phrase cache relationship
    cache_id = get_uuid_column(
        ForeignKey("ir_ai_phrase_cache.cache_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Operation-specific validation flags
    validation_passed = Column(Boolean, nullable=True)  # Whether generated content passed validation
    vote_correct = Column(Boolean, nullable=True)  # Whether AI vote was correct (for analysis)

    # Relationships
    phrase_cache = relationship("IRAIPhraseCache", back_populates="metrics")

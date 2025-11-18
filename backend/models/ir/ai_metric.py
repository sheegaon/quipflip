"""IR AIMetric model."""
from sqlalchemy import ForeignKey
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

    # Relationships
    phrase_cache = relationship("IRAIPhraseCache", back_populates="metrics")

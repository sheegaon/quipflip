"""AI metrics model for tracking AI usage, costs, and performance."""

from sqlalchemy import Index, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.ai_metric_base import AIMetricBase
from backend.models.base import get_uuid_column


class QFAIMetric(AIMetricBase):
    """
    AI metrics model for tracking AI usage and performance.

    Tracks individual AI operations (copy generation, voting) with
    provider, cost, latency, and success information.
    """
    __tablename__ = "qf_ai_metrics"

    # Link to phrase cache (QF-specific)
    cache_id = get_uuid_column(
        ForeignKey("qf_ai_phrase_cache.cache_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    phrase_cache = relationship("QFAIPhraseCache", foreign_keys=[cache_id], backref="metrics")

    # Indexes for common queries
    __table_args__ = (
        Index('ix_ai_metrics_created_at_success', 'created_at', 'success'),
        Index('ix_ai_metrics_operation_provider', 'operation_type', 'provider'),
        Index('ix_ai_metrics_op_created', 'operation_type', 'created_at'),  # For analytics queries
    )

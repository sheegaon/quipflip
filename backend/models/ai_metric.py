"""AI metrics model for tracking AI usage, costs, and performance."""

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Index
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class AIMetric(Base):
    """
    AI metrics model for tracking AI usage and performance.

    Tracks individual AI operations (copy generation, voting) with
    provider, cost, latency, and success information.
    """
    __tablename__ = "ai_metrics"

    metric_id = get_uuid_column(primary_key=True, default=uuid.uuid4)

    # Operation details
    operation_type = Column(String(50), nullable=False, index=True)  # "copy_generation" or "vote_generation"
    provider = Column(String(50), nullable=False, index=True)  # "openai" or "gemini"
    model = Column(String(100), nullable=False)  # e.g., "gpt-5-nano", "gemini-2.5-flash-lite"

    # Performance metrics
    success = Column(Boolean, nullable=False, index=True)  # Whether operation succeeded
    latency_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    error_message = Column(String(500), nullable=True)  # Error message if failed

    # Cost tracking
    estimated_cost_usd = Column(Float, nullable=True)  # Estimated cost in USD

    # Context (optional, for analysis)
    prompt_length = Column(Integer, nullable=True)  # Length of prompt in characters
    response_length = Column(Integer, nullable=True)  # Length of response in characters

    # For copy generation
    validation_passed = Column(Boolean, nullable=True)  # Whether generated phrase passed validation

    # For vote generation
    vote_correct = Column(Boolean, nullable=True)  # Whether AI vote was correct (for analysis)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    # Indexes for common queries
    __table_args__ = (
        Index('ix_ai_metrics_created_at_success', 'created_at', 'success'),
        Index('ix_ai_metrics_operation_provider', 'operation_type', 'provider'),
        Index('ix_ai_metrics_op_created', 'operation_type', 'created_at'),  # For analytics queries
    )

    def __repr__(self):
        return f"<AIMetric(operation={self.operation_type}, provider={self.provider}, success={self.success})>"

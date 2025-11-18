"""Base AIMetric model with common fields and functionality."""
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    Index,
    ForeignKey,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class AIMetricBase(Base):
    """Base AI metrics model for tracking AI usage, costs, and performance."""

    __abstract__ = True

    metric_id = get_uuid_column(primary_key=True, default=uuid.uuid4)

    # Operation details
    operation_type = Column(String(50), nullable=False, index=True)  # "copy_generation", "vote_generation", "hint_generation", "backronym_generation"
    provider = Column(String(50), nullable=False, index=True)  # "openai", "gemini"
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

    # Operation-specific validation flags
    validation_passed = Column(Boolean, nullable=True)  # Whether generated content passed validation
    vote_correct = Column(Boolean, nullable=True)  # Whether AI vote was correct (for analysis)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    def __repr__(self):
        return f"<{self.__class__.__name__}(operation={self.operation_type}, provider={self.provider}, success={self.success})>"
"""Prompt library model."""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Float
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class Prompt(Base):
    """Prompt library model."""
    __tablename__ = "qf_prompts"

    prompt_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    text = Column(String(500), unique=True, nullable=False)
    category = Column(String(50), nullable=False)  # simple, deep, silly, fun, abstract
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    usage_count = Column(Integer, default=0, nullable=False)
    avg_copy_quality = Column(Float, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)

    # Relationships
    rounds = relationship("Round", back_populates="prompt")

    def __repr__(self):
        return f"<Prompt(prompt_id={self.prompt_id}, text='{self.text[:30]}...')>"

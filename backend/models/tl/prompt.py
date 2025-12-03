"""ThinkLink prompt model."""
from sqlalchemy import Column, String, DateTime, Boolean, Index
from datetime import datetime, UTC
from pgvector.sqlalchemy import Vector
from backend.database import Base
from backend.models.base import get_uuid_column


class TLPrompt(Base):
    """ThinkLink prompt corpus.

    Contains the prompts players will guess answers for, along with
    embeddings for on-topic validation.
    """

    __tablename__ = "tl_prompt"

    prompt_id = get_uuid_column(primary_key=True)
    text = Column(String(500), nullable=False, index=True)
    embedding = Column(Vector(1536), nullable=True)  # For on-topic checks
    is_active = Column(Boolean, default=True, nullable=False)
    ai_seeded = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index('idx_tl_prompt_active', 'is_active'),
        Index('idx_tl_prompt_text', 'text'),
    )

    def __repr__(self):
        return f"<TLPrompt(prompt_id={self.prompt_id}, text='{self.text[:30]}...')>"

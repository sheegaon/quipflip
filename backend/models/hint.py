"""Database model for AI-generated copy hints."""
from datetime import datetime, UTC
import uuid

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class Hint(Base):
    """Stores AI-generated hint phrases for a prompt round."""

    __tablename__ = "hints"

    hint_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    # Note: prompt_round_id is indexed via composite index in __table_args__
    prompt_round_id = get_uuid_column(
        ForeignKey("rounds.round_id", ondelete="CASCADE"),
        nullable=False,
    )
    hint_phrases = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    generation_provider = Column(String(20), nullable=False)
    generation_model = Column(String(100), nullable=True)

    prompt_round = relationship("Round", back_populates="hints")

    __table_args__ = (
        UniqueConstraint("prompt_round_id", name="uq_hints_prompt_round"),
        Index("ix_hints_prompt_round_id_created", "prompt_round_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Hint(hint_id={self.hint_id}, prompt_round_id={self.prompt_round_id})>"


"""ThinkLink answer model."""
from sqlalchemy import Column, ForeignKey, String, Integer, DateTime, Boolean, Index
from datetime import datetime, UTC
from pgvector.sqlalchemy import Vector
from backend.database import Base
from backend.models.base import get_uuid_column


class TLAnswer(Base):
    """ThinkLink answer corpus.

    Represents an answer submitted by a player or AI for a prompt.
    Includes embedding for semantic matching and cluster assignment.
    """

    __tablename__ = "tl_answer"

    answer_id = get_uuid_column(primary_key=True)
    prompt_id = get_uuid_column(
        ForeignKey("tl_prompt.prompt_id", ondelete="CASCADE"),
        nullable=False
    )
    text = Column(String(200), nullable=False)
    embedding = Column(Vector(1536), nullable=False)
    cluster_id = get_uuid_column(
        ForeignKey("tl_cluster.cluster_id", ondelete="SET NULL"),
        nullable=True
    )

    # Stats for usefulness calculation
    answer_players_count = Column(Integer, default=0, nullable=False)  # Distinct players who submitted this exact answer
    shows = Column(Integer, default=0, nullable=False)  # Times this answer appeared in a snapshot
    contributed_matches = Column(Integer, default=0, nullable=False)  # Times someone matched this answer

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index('idx_tl_answer_prompt', 'prompt_id'),
        Index('idx_tl_answer_cluster', 'cluster_id'),
        Index('idx_tl_answer_active', 'is_active', 'prompt_id'),
    )

    def __repr__(self):
        return f"<TLAnswer(answer_id={self.answer_id}, text='{self.text[:30]}...')>"

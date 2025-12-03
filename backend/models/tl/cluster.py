"""ThinkLink cluster model."""
from sqlalchemy import Column, ForeignKey, Integer, DateTime, Index
from datetime import datetime, UTC
from pgvector.sqlalchemy import Vector
from backend.database import Base
from backend.models.base import get_uuid_column


class TLCluster(Base):
    """ThinkLink semantic cluster.

    Represents a semantic cluster of answer within a prompt.
    Each cluster has a centroid embedding and tracks its size.
    """

    __tablename__ = "tl_cluster"

    cluster_id = get_uuid_column(primary_key=True)
    prompt_id = get_uuid_column(
        ForeignKey("tl_prompt.prompt_id", ondelete="CASCADE"),
        nullable=False
    )
    centroid_embedding = Column(Vector(1536), nullable=False)
    size = Column(Integer, default=1, nullable=False)
    example_answer_id = get_uuid_column(nullable=True)  # FK to tl_answer, lazy reference
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index('idx_tl_cluster_prompt', 'prompt_id'),
    )

    def __repr__(self):
        return f"<TLCluster(cluster_id={self.cluster_id}, prompt_id={self.prompt_id}, size={self.size})>"

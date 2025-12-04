"""ThinkLink guess model."""
import uuid
from sqlalchemy import Column, ForeignKey, String, DateTime, Boolean, JSON, Index
from datetime import datetime, UTC
from pgvector.sqlalchemy import Vector
from backend.database import Base
from backend.models.base import get_uuid_column


class TLGuess(Base):
    """ThinkLink guess log.

    Records each guess submitted during a round for post-game review
    and debugging. Includes embedding and match results.
    """

    __tablename__ = "tl_guess"

    guess_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    round_id = get_uuid_column(
        ForeignKey("tl_round.round_id", ondelete="CASCADE"),
        nullable=False
    )
    text = Column(String(200), nullable=False)
    embedding = Column(Vector(1536), nullable=False)

    # Match results
    was_match = Column(Boolean, nullable=False)  # Did it match any snapshot answers?
    matched_answer_ids = Column(JSON, nullable=False, default=[])  # Answers it matched
    matched_cluster_ids = Column(JSON, nullable=False, default=[])  # Clusters it matched
    caused_strike = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index('idx_tl_guess_round', 'round_id'),
    )

    def __repr__(self):
        return f"<TLGuess(guess_id={self.guess_id}, text='{self.text[:30]}...', was_match={self.was_match})>"

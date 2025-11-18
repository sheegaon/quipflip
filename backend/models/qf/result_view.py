"""Result view tracking for idempotent prize collection."""
from sqlalchemy import Column, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class QFResultView(Base):
    """Result view tracking model."""
    __tablename__ = "qf_result_views"

    view_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    phraseset_id = get_uuid_column(ForeignKey("qf_phrasesets.phraseset_id"), nullable=False, index=True)
    player_id = get_uuid_column(ForeignKey("qf_players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    result_viewed = Column(Boolean, default=False, nullable=False, index=True)
    payout_amount = Column(Integer, nullable=False)
    viewed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    first_viewed_at = Column(DateTime(timezone=True), nullable=True)
    result_viewed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    phraseset = relationship("Phraseset", back_populates="result_views")
    player = relationship("QFPlayer", back_populates="result_views")

    # Constraints - one view per player per phraseset
    __table_args__ = (
        UniqueConstraint('player_id', 'phraseset_id', name='uq_player_phraseset_result'),
    )

    def __repr__(self):
        return f"<ResultView(view_id={self.view_id}, viewed={self.result_viewed})>"

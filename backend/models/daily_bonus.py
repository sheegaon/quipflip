"""Daily bonus tracking model."""
from sqlalchemy import Column, Integer, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class DailyBonus(Base):
    """Daily bonus tracking model."""
    __tablename__ = "qf_daily_bonuses"

    bonus_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(ForeignKey("qf_players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, default=100, nullable=False)
    claimed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    date = Column(Date, nullable=False, index=True)  # UTC date

    # Relationships
    player = relationship("Player", back_populates="daily_bonuses")

    # Constraints - one bonus per player per day
    __table_args__ = (
        UniqueConstraint('player_id', 'date', name='uq_player_daily_bonus'),
    )

    def __repr__(self):
        return f"<DailyBonus(bonus_id={self.bonus_id}, player_id={self.player_id}, date={self.date})>"

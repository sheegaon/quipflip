"""Tracks per-player daily free caption quotas."""
from datetime import datetime, UTC

from sqlalchemy import Column, Date, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class MMPlayerDailyState(Base):
    """Per-player daily counters for free caption submissions."""

    __tablename__ = "mm_player_daily_states"

    player_id = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="CASCADE"), primary_key=True
    )
    date = Column(Date, primary_key=True, default=lambda: datetime.now(UTC).date())
    free_captions_used = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    player = relationship("MMPlayer", back_populates="daily_states")

    __table_args__ = (
        Index("ix_mm_player_daily_state_date", "date"),
    )

    def __repr__(self) -> str:
        return (
            f"<MMPlayerDailyState(player_id={self.player_id}, date={self.date}, "
            f"free_captions_used={self.free_captions_used})>"
        )

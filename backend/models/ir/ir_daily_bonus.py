"""IR DailyBonus model."""
from sqlalchemy import (
    Column,
    Integer,
    Date,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class IRDailyBonus(Base):
    """Daily login bonus tracking for IR."""

    __tablename__ = "ir_daily_bonuses"

    bonus_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bonus_amount = Column(Integer, default=100, nullable=False)
    claimed_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    date = Column(Date, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("player_id", "date", name="uq_ir_daily_bonus_player_date"),
        Index("ix_ir_daily_bonus_player_id", player_id),
        Index("ix_ir_daily_bonus_date", date),
    )

    # Relationships
    player = relationship("IRPlayer", back_populates="daily_bonuses")

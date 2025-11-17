"""Daily bonus tracking model."""
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.models.daily_bonus_base import DailyBonusBase
from backend.models.base import get_uuid_column


class IRDailyBonus(DailyBonusBase):
    """Daily bonus tracking model."""
    __tablename__ = "ir_daily_bonuses"

    # Override player_id to add IR-specific foreign key constraint
    player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    player = relationship("Player", back_populates="daily_bonuses")

    # Constraints - one bonus per player per day
    __table_args__ = (
        UniqueConstraint('player_id', 'date', name='uq_player_daily_bonus'),
    )

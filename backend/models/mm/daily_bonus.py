"""Daily bonus tracking for Meme Mint players."""
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.models.daily_bonus_base import DailyBonusBase
from backend.models.base import get_uuid_column


class MMDailyBonus(DailyBonusBase):
    """Daily bonus tracking model for Meme Mint."""

    __tablename__ = "mm_daily_bonuses"

    player_id = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="CASCADE"), nullable=False
    )

    player = relationship("MMPlayer", back_populates="daily_bonuses")

    __table_args__ = (
        UniqueConstraint("player_id", "date", name="uq_mm_player_daily_bonus"),
    )
